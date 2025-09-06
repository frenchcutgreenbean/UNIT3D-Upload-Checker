from .hdr_formats import (
    SDR,
    HDR,
    HDR10_PLUS,
    DOLBY_VISION,
    DOLBY_VISION_HDR,
    DOLBY_VISION_HDR10P,
)

WEB_SLOTS = {
    SDR: [SDR],  # 1 Slot for SDR
    DOLBY_VISION: [DOLBY_VISION],  # 1 Slot for DV
    # 1 Slot for HDR ordered in terms of trumping
    HDR: {0: HDR, 1: HDR10_PLUS, 2: DOLBY_VISION_HDR, 3: DOLBY_VISION_HDR10P},
}

# Encode trumping order
ENCODE_SLOTS = {
    0: SDR,
    1: HDR,
    2: HDR10_PLUS,
    3: DOLBY_VISION,
    4: DOLBY_VISION_HDR,
    5: DOLBY_VISION_HDR10P,
}

# Remux trumping order
REMUX_SLOTS = {
    0: SDR,
    1: HDR,
    2: HDR10_PLUS,
    3: DOLBY_VISION,
    4: DOLBY_VISION_HDR,
    5: DOLBY_VISION_HDR10P,
}


class SlotChecker:
    def __init__(self):
        self.web_slots = WEB_SLOTS
        self.encode_slots = ENCODE_SLOTS
        self.remux_slots = REMUX_SLOTS

    def is_hdr_slot_upgrade(self, file_tuple, existing_tuples):
        """
        Check if a file with the given attributes fills a new slot or upgrades an existing one.

        Args:
            file_tuple: (quality, resolution, hdr_format) tuple for the new file
            existing_tuples: List of (quality, resolution, hdr_format) tuples

        Returns:
            tuple: (is_upgrade, reason)
        """
        from .hdr_formats import (
            SDR,
            HDR,
            HDR10_PLUS,
            DOLBY_VISION,
            DOLBY_VISION_HDR,
            DOLBY_VISION_HDR10P,
        )
        from .hdr_formats import HDR_HIERARCHY

        # Normalize inputs
        source_type = self._map_quality_to_source_type(file_tuple[0])
        resolution = file_tuple[1].lower()
        hdr_format = file_tuple[2]

        # Skip non-4K content - this should be handled by the caller but double check
        if not ("2160" in resolution or "4k" in resolution.lower()):
            return False, "Not 4K content"

        # Normalize the HDR format
        normalized_file_hdr = self._normalize_hdr_format(hdr_format)

        # Get the hierarchy rank of the file's HDR format
        try:
            file_hdr_rank = HDR_HIERARCHY.index(normalized_file_hdr)
        except ValueError:
            # If format not in hierarchy, default to lowest rank
            file_hdr_rank = -1

        # Handle WEB releases differently than REMUX and ENCODE
        if source_type == "WEB":
            # For WEB, we need to determine which slot this belongs to
            slot_id = self._get_slot_id(source_type, hdr_format)
            if not slot_id:
                return False, f"No matching slot for {source_type} with {hdr_format}"

            # Check if any files exist in this slot already
            existing_in_slot = []
            highest_rank_in_slot = -1
            highest_format_in_slot = None

            # Also check if there's a better format in ANY slot
            best_existing_format = None
            best_existing_rank = -1

            for q, r, h in existing_tuples:
                ex_source = self._map_quality_to_source_type(q)

                # Only consider same source type and 4K resolution
                if ex_source != source_type or "2160" not in r.lower():
                    continue

                # Normalize the existing format
                ex_normalized = self._normalize_hdr_format(h)
                try:
                    ex_rank = HDR_HIERARCHY.index(ex_normalized)

                    # Check if this is the best format overall (across all slots)
                    if ex_rank > best_existing_rank:
                        best_existing_rank = ex_rank
                        best_existing_format = h

                    # Get the slot for this existing file
                    ex_slot_id = self._get_slot_id(ex_source, h)
                    if ex_slot_id != slot_id:
                        continue

                    # This file is in the same slot
                    existing_in_slot.append(h)

                    # Check if it's the highest ranked in this slot
                    if ex_rank > highest_rank_in_slot:
                        highest_rank_in_slot = ex_rank
                        highest_format_in_slot = h
                except ValueError:
                    continue

            # If slot is empty, this is a new slot
            if not existing_in_slot:
                # BUT - if there's a better format in another slot, this is not an upgrade
                if best_existing_rank > file_hdr_rank:
                    return (
                        False,
                        f"Better format already exists in another slot: {best_existing_format}",
                    )
                return True, f"New {source_type} slot: {hdr_format}"

            # If file's HDR format rank is higher than any existing in this slot, it's an upgrade
            # BUT only if there isn't a better format in another slot
            if file_hdr_rank > highest_rank_in_slot:
                # Double-check against ALL formats again to be safe
                if best_existing_rank > file_hdr_rank:
                    return (
                        False,
                        f"Better format already exists in another slot: {best_existing_format}",
                    )
                return (
                    True,
                    f"Upgrade in {source_type} slot: {hdr_format} trumps {highest_format_in_slot}",
                )

            return (
                False,
                f"Slot already occupied with equal or better format: {highest_format_in_slot}",
            )

        # For REMUX and ENCODE, a file is only an upgrade if it trumps ALL existing files
        else:  # source_type is REMUX or ENCODE
            # Get all existing files with matching source type and 4K resolution
            matching_formats = []
            best_existing_format = None
            best_existing_rank = -1

            for q, r, h in existing_tuples:
                ex_source = self._map_quality_to_source_type(q)

                # Only consider same source type and 4K resolution
                if ex_source != source_type or "2160" not in r.lower():
                    continue

                # Add to our collection of matching formats
                matching_formats.append(h)

                # Keep track of best format for better error message
                ex_normalized = self._normalize_hdr_format(h)
                try:
                    ex_rank = HDR_HIERARCHY.index(ex_normalized)
                    if ex_rank > best_existing_rank:
                        best_existing_rank = ex_rank
                        best_existing_format = h
                except ValueError:
                    continue

            # If no matching files, this is automatically a new slot
            if not matching_formats:
                return True, f"New {source_type} format: {hdr_format}"

            # For each existing format, check if our file has a higher rank
            for existing_format in matching_formats:
                ex_normalized = self._normalize_hdr_format(existing_format)

                try:
                    ex_rank = HDR_HIERARCHY.index(ex_normalized)

                    # For REMUX and ENCODE - strict requirement:
                    # If ANY existing format has equal or higher rank than our file,
                    # then our file is not an upgrade
                    if ex_rank >= file_hdr_rank:
                        return (
                            False,
                            f"Equal or better format already exists: {existing_format}",
                        )
                except ValueError:
                    # Format not in hierarchy, skip
                    continue

            # If we got here, our file trumps ALL existing files
            return (
                True,
                f"Upgrade for {source_type}: {hdr_format} trumps all existing formats",
            )

    def _map_quality_to_source_type(self, quality):
        """Map quality string to source type."""
        quality = quality.lower()
        if any(x in quality for x in ["web-dl", "webdl", "webrip"]):
            return "WEB"
        elif "remux" in quality:
            return "REMUX"
        elif any(x in quality for x in ["encode"]):
            return "ENCODE"
        return "UNKNOWN"

    def _get_slot_id(self, source_type, hdr_format):
        """Get slot ID for given source type and HDR Format."""
        slots = None
        if source_type == "WEB":
            slots = self.web_slots
        elif source_type == "ENCODE":
            slots = self.encode_slots
        elif source_type == "REMUX":
            slots = self.remux_slots
        else:
            return None

        # For Web, handle special case of slot types
        if source_type == "WEB":
            # Normalize the HDR format first
            normalized_format = self._normalize_hdr_format(hdr_format)

            # Web has 3 slots: SDR, DV, and HDR (which includes HDR, HDR10+, DV+HDR, DV+HDR10+)
            if normalized_format == SDR:
                return "SDR"
            elif normalized_format == DOLBY_VISION:
                return "DV"
            elif normalized_format in [
                HDR,
                HDR10_PLUS,
                DOLBY_VISION_HDR,
                DOLBY_VISION_HDR10P,
            ]:
                return "HDR"  # All HDR variants go to the HDR slot

            # Fallback
            if not hdr_format:
                return "SDR"
            return "SDR"

        # For Encode and Remux, find the value in slots dict
        for slot_id, slot_type in slots.items():
            if self._is_matching_hdr_format(hdr_format, slot_type):
                return slot_id
        return None

    def _is_matching_hdr_format(self, hdr_format, slot_type):
        """Check if HDR Format matches slot type."""
        from .hdr_formats import SDR, HDR, HDR10_PLUS, DOLBY_VISION, DOLBY_VISION_HDR

        if not hdr_format:
            return slot_type == SDR

        # Normalize the input HDR format to match our constants
        normalized_format = self._normalize_hdr_format(hdr_format)

        return normalized_format == slot_type

    def _normalize_hdr_format(self, hdr_format):
        """Normalize HDR format string to match our constants."""
        from .hdr_formats import (
            SDR,
            HDR,
            HDR10_PLUS,
            DOLBY_VISION,
            DOLBY_VISION_HDR,
            DOLBY_VISION_HDR10P,
        )

        if not hdr_format:
            return SDR

        hdr_lower = hdr_format.lower()

        # Check for combined formats first
        if "dv" in hdr_lower or "dolby vision" in hdr_lower:
            if "hdr10+" in hdr_lower:
                return DOLBY_VISION_HDR10P
            elif "hdr" in hdr_lower or "hdr10" in hdr_lower:
                return DOLBY_VISION_HDR
            else:
                return DOLBY_VISION
        # Then check for individual formats
        elif "hdr10+" in hdr_lower:
            return HDR10_PLUS
        elif "hdr" in hdr_lower or "hdr10" in hdr_lower:
            return HDR

        return SDR

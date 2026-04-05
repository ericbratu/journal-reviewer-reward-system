from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional


ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
BOX_BORDER_RE = re.compile(r"^[\s\+\-\=╭╮╯╰├┤┬┴┼│┃┆┊┄┈─━╞╡╪]+$")
FLOAT_RE = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


@dataclass
class SubnetEntry:
    uid: int
    emission: float
    role: str = "unknown"
    hotkey: Optional[str] = None
    coldkey: Optional[str] = None
    stake: Optional[float] = None
    rank: Optional[float] = None
    trust: Optional[float] = None
    incentive: Optional[float] = None
    dividends: Optional[float] = None
    validator_permit: Optional[bool] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SubnetSnapshot:
    fetched_at: float
    command: List[str]
    entries: List[SubnetEntry]
    source: str
    raw_output: str
    netuid: Optional[str]
    network: Optional[str]

    def to_dict(self, limit: Optional[int] = None) -> Dict[str, Any]:
        entries = self.entries[:limit] if limit is not None else self.entries
        return {
            "fetched_at": self.fetched_at,
            "command": self.command,
            "source": self.source,
            "netuid": self.netuid,
            "network": self.network,
            "count": len(self.entries),
            "entries": [asdict(entry) for entry in entries],
        }


class SubnetStatsService:
    def __init__(
        self,
        netuid: Optional[str] = None,
        network: Optional[str] = None,
        command: Optional[List[str]] = None,
        cache_ttl: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
    ) -> None:
        self.netuid = netuid or os.getenv("SUBNET_NETUID") or os.getenv("NETUID")
        self.network = (
            network or os.getenv("SUBNET_NETWORK") or os.getenv("ENDPOINT")
        )
        self.command = command or self._build_command()
        self.netuid = self._extract_command_option("--netuid") or self.netuid
        self.network = self._extract_command_option("--network") or self.network
        self.validator_uids = self._parse_uid_set(
            os.getenv("SUBNET_VALIDATOR_UIDS", "0,6")
        )
        self.cache_ttl = cache_ttl or int(os.getenv("SUBNET_CACHE_TTL", "45"))
        self.timeout_seconds = timeout_seconds or int(
            os.getenv("SUBNET_COMMAND_TIMEOUT", "30")
        )
        self._lock = threading.Lock()
        self._snapshot: Optional[SubnetSnapshot] = None

    def _build_command(self) -> List[str]:
        custom_command = os.getenv("SUBNET_STATS_COMMAND")
        if custom_command:
            try:
                parsed = json.loads(custom_command)
                if isinstance(parsed, list) and all(
                    isinstance(item, str) for item in parsed
                ):
                    return parsed
            except json.JSONDecodeError:
                pass
            return custom_command.split()

        cli = os.getenv("SUBNET_CLI", "btcli")
        command = [cli, "subnet", "show"]
        if self.netuid:
            command.extend(["--netuid", self.netuid])
        if self.network:
            command.extend(["--network", self.network])
        return command

    def get_snapshot(self, force_refresh: bool = False) -> SubnetSnapshot:
        with self._lock:
            if (
                not force_refresh
                and self._snapshot is not None
                and time.time() - self._snapshot.fetched_at < self.cache_ttl
            ):
                return self._snapshot

            raw_output = self._run_command()
            entries, source = self._parse_output(raw_output)
            snapshot = SubnetSnapshot(
                fetched_at=time.time(),
                command=self.command,
                entries=sorted(
                    entries, key=lambda item: item.emission, reverse=True
                ),
                source=source,
                raw_output=raw_output,
                netuid=self.netuid,
                network=self.network,
            )
            self._snapshot = snapshot
            return snapshot

    def _run_command(self) -> str:
        completed = subprocess.run(
            self.command,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            check=True,
        )
        return completed.stdout

    def _parse_output(self, raw_output: str) -> tuple[List[SubnetEntry], str]:
        stripped = ANSI_ESCAPE_RE.sub("", raw_output).strip()
        if not stripped:
            raise ValueError("The subnet command returned no output.")

        json_entries = self._extract_entries_from_json_payload(stripped)
        if json_entries:
            return json_entries, "json"

        table_entries = self._extract_entries_from_table(stripped)
        if table_entries:
            return table_entries, "table"

        raise ValueError(
            "Could not find UID/emission rows in the subnet command output."
        )

    def _extract_entries_from_json_payload(
        self, payload: str
    ) -> List[SubnetEntry]:
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return []
        return self._entries_from_json(data)

    def _entries_from_json(self, data: Any) -> List[SubnetEntry]:
        entries: List[SubnetEntry] = []

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                maybe_entry = self._entry_from_mapping(node)
                if maybe_entry is not None:
                    entries.append(maybe_entry)
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(data)

        deduped: Dict[int, SubnetEntry] = {}
        for entry in entries:
            deduped[entry.uid] = entry
        return list(deduped.values())

    def _entry_from_mapping(
        self, mapping: Dict[str, Any]
    ) -> Optional[SubnetEntry]:
        lowered = {self._normalize_key(key): value for key, value in mapping.items()}
        uid = self._extract_int(lowered.get("uid"))
        emission_value = self._first_present(
            lowered, "emission", "emissions", "emissiontao"
        )
        emission = self._extract_float(emission_value)
        if uid is None or emission is None:
            return None

        validator_permit = self._extract_bool(
            self._first_present(lowered, "validatorpermit", "vpermit")
        )
        role = "validator" if validator_permit else "miner"
        if validator_permit is None:
            role = str(lowered.get("role") or lowered.get("type") or "unknown")
        if uid in self.validator_uids:
            role = "validator"
        elif role == "unknown":
            role = "miner"

        return SubnetEntry(
            uid=uid,
            emission=emission,
            role=role,
            hotkey=self._extract_string(lowered.get("hotkey")),
            coldkey=self._extract_string(lowered.get("coldkey")),
            stake=self._extract_float(lowered.get("stake")),
            rank=self._extract_float(lowered.get("rank")),
            trust=self._extract_float(lowered.get("trust")),
            incentive=self._extract_float(lowered.get("incentive")),
            dividends=self._extract_float(lowered.get("dividends")),
            validator_permit=validator_permit,
            raw=mapping,
        )

    def _extract_entries_from_table(self, payload: str) -> List[SubnetEntry]:
        lines = [line.rstrip() for line in payload.splitlines() if line.strip()]
        header_cells: Optional[List[str]] = None
        entries: List[SubnetEntry] = []

        for line in lines:
            if BOX_BORDER_RE.match(line.strip()):
                continue

            cells = self._split_unicode_table_row(line) or self._split_table_row(line)
            if len(cells) < 2:
                continue

            if self._looks_like_table_header(cells):
                header_cells = cells
                continue

            if header_cells is not None and len(cells) >= len(header_cells):
                row_mapping = {
                    self._normalize_key(header_cells[idx]): cells[idx]
                    for idx in range(min(len(header_cells), len(cells)))
                }
                maybe_entry = self._entry_from_mapping(row_mapping)
            else:
                maybe_entry = self._entry_from_btcli_row(cells)

            if maybe_entry is not None:
                entries.append(maybe_entry)

        return entries

    def _split_table_row(self, line: str) -> List[str]:
        if "│" in line:
            parts = line.split("│")
        elif "|" in line:
            parts = line.split("|")
        else:
            parts = re.split(r"\s{2,}", line.strip())
        return [part.strip() for part in parts if part.strip()]

    def _normalize_key(self, value: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "", value.lower())
        aliases = {
            "u": "uid",
            "ui": "uid",
            "coldk": "coldkey",
            "dividen": "dividends",
            "dividend": "dividends",
            "emissions": "emission",
        }
        return aliases.get(normalized, normalized)

    def _split_unicode_table_row(self, line: str) -> List[str]:
        if "┃" in line:
            return [part.strip() for part in line.split("┃") if part.strip()]
        if "│" in line:
            return [part.strip() for part in line.split("│") if part.strip()]
        return []

    def _looks_like_table_header(self, cells: List[str]) -> bool:
        normalized_cells = [self._normalize_key(cell) for cell in cells]
        has_uid = any(cell == "uid" or cell.startswith("u") for cell in normalized_cells)
        has_emission = any("emission" in cell for cell in normalized_cells)
        has_hotkey = any("hotkey" in cell for cell in normalized_cells)
        return has_uid and has_emission and has_hotkey

    def _entry_from_btcli_row(self, cells: List[str]) -> Optional[SubnetEntry]:
        if len(cells) < 8:
            return None

        uid = self._extract_int(cells[0])
        emission = self._extract_float(cells[6])
        if uid is None or emission is None:
            return None

        identity = cells[9] if len(cells) > 9 else None
        role = "validator" if uid in self.validator_uids else "miner"
        if identity and "validator" in identity.lower():
            role = "validator"

        return SubnetEntry(
            uid=uid,
            emission=emission,
            role=role,
            hotkey=self._extract_string(cells[7] if len(cells) > 7 else None),
            coldkey=self._extract_string(cells[8] if len(cells) > 8 else None),
            stake=self._extract_float(cells[1] if len(cells) > 1 else None),
            dividends=self._extract_float(cells[4] if len(cells) > 4 else None),
            incentive=self._extract_float(cells[5] if len(cells) > 5 else None),
            raw={"cells": cells},
        )

    def _first_present(self, mapping: Dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in mapping:
                return mapping[key]
        return None

    def _extract_command_option(self, option_name: str) -> Optional[str]:
        try:
            option_index = self.command.index(option_name)
        except ValueError:
            return None

        value_index = option_index + 1
        if value_index >= len(self.command):
            return None
        return self.command[value_index]

    def _parse_uid_set(self, raw_value: str) -> set[int]:
        values: set[int] = set()
        for part in raw_value.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                values.add(int(part))
            except ValueError:
                continue
        return values

    def _extract_string(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _extract_int(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        match = re.search(r"\d+", str(value))
        return int(match.group(0)) if match else None

    def _extract_float(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)

        text = str(value).replace(",", "").strip()
        match = FLOAT_RE.search(text)
        return float(match.group(0)) if match else None

    def _extract_bool(self, value: Any) -> Optional[bool]:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in {"true", "yes", "1", "y", "validator"}:
            return True
        if text in {"false", "no", "0", "n", "miner"}:
            return False
        return None


def build_summary(entries: Iterable[SubnetEntry]) -> Dict[str, Any]:
    entry_list = list(entries)
    if not entry_list:
        return {
            "top_emission": 0.0,
            "total_emission": 0.0,
            "validator_count": 0,
            "miner_count": 0,
        }

    return {
        "top_emission": max(entry.emission for entry in entry_list),
        "total_emission": sum(entry.emission for entry in entry_list),
        "validator_count": sum(1 for entry in entry_list if entry.role == "validator"),
        "miner_count": sum(1 for entry in entry_list if entry.role == "miner"),
    }

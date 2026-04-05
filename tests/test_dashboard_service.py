import json

from subnet_dashboard.service import SubnetStatsService, build_summary


def test_parses_table_output():
    service = SubnetStatsService(command=["echo"])
    output = """
    ╭────┬──────────────┬────────────┬────────────┬─────────╮
    │ UID│ HOTKEY       │ EMISSION   │ STAKE      │ VPERMIT │
    ├────┼──────────────┼────────────┼────────────┼─────────┤
    │ 7  │ 5FAbc123456  │ 12.345600  │ 998.20     │ True    │
    │ 2  │ 5FXyz999999  │ 8.450000   │ 120.00     │ False   │
    ╰────┴──────────────┴────────────┴────────────┴─────────╯
    """

    entries, source = service._parse_output(output)

    assert source == "table"
    assert [entry.uid for entry in entries] == [7, 2]
    assert entries[0].role == "validator"
    assert entries[1].role == "miner"
    assert entries[0].emission == 12.3456


def test_parses_json_output():
    service = SubnetStatsService(command=["echo"])
    output = json.dumps(
        {
            "neurons": [
                {
                    "uid": 4,
                    "emission": 5.5,
                    "hotkey": "hk4",
                    "validator_permit": False,
                },
                {
                    "uid": 9,
                    "emission": 8.1,
                    "hotkey": "hk9",
                    "validator_permit": True,
                },
            ]
        }
    )

    entries, source = service._parse_output(output)

    assert source == "json"
    assert [entry.uid for entry in entries] == [4, 9]
    assert entries[1].role == "validator"


def test_build_summary_counts_roles():
    service = SubnetStatsService(command=["echo"])
    entries, _ = service._parse_output(
        json.dumps(
            {
                "rows": [
                    {"uid": 1, "emission": 3.0, "validator_permit": True},
                    {"uid": 2, "emission": 1.5, "validator_permit": False},
                ]
            }
        )
    )

    summary = build_summary(entries)

    assert summary["top_emission"] == 3.0
    assert summary["total_emission"] == 4.5
    assert summary["validator_count"] == 1
    assert summary["miner_count"] == 1


def test_parses_real_btcli_table_shape():
    service = SubnetStatsService(command=["echo"])
    output = """
                                                     Subnet 2: ALAN
                                              Network: local • Mechanism 0

 U… ┃ Stake (… ┃ Alpha (… ┃ Tao (τ) ┃ Dividen… ┃ Incentive ┃ Emissions (… ┃ Hotkey ┃ Coldk… ┃ Identity      ┃ Claim Ty…
━━━━╇━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━
 0  │ 15.88k β │ 15.88k β │  τ 0.00 │ 0.000000 │ 0.000000  │  2.215754 β  │ 5D1pdQ │ 5CVM6F │ ALAN (*Owner) │     -
 6  │ 29.85k β │ 29.85k β │  τ 0.00 │ 0.000000 │ 0.000000  │  4.165723 β  │ 5H99rY │ 5Ci8ui │ ~             │     -
 2  │  3.71k β │  3.71k β │  τ 0.00 │ 0.000000 │ 0.000000  │  0.517408 β  │ 5HRHqA │ 5HGPue │ ~             │     -
────┼──────────┼──────────┼─────────┼──────────┼───────────┼──────────────┼────────┼────────┼───────────────┼───────────
    │ 64.63k β │ 64.63k β │  0.00 β │  0.000   │           │   9.0201 β   │        │        │               │
    """

    entries, source = service._parse_output(output)

    assert source == "table"
    assert [entry.uid for entry in entries] == [0, 6, 2]
    assert entries[0].emission == 2.215754
    assert entries[1].emission == 4.165723
    assert entries[0].hotkey == "5D1pdQ"


def test_command_override_sets_displayed_netuid_and_network():
    service = SubnetStatsService(
        netuid="123",
        network="finney",
        command=[
            "btcli",
            "subnet",
            "show",
            "--netuid",
            "2",
            "--network",
            "ws://127.0.0.1:9944",
        ],
    )

    assert service.netuid == "2"
    assert service.network == "ws://127.0.0.1:9944"


def test_btcli_rows_assign_validator_roles_from_uid_list():
    service = SubnetStatsService(command=["echo"])
    output = """
                                                     Subnet 2: ALAN
                                              Network: local • Mechanism 0

 U… ┃ Stake (… ┃ Alpha (… ┃ Tao (τ) ┃ Dividen… ┃ Incentive ┃ Emissions (… ┃ Hotkey ┃ Coldk… ┃ Identity      ┃ Claim Ty…
━━━━╇━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━
 0  │ 15.88k β │ 15.88k β │  τ 0.00 │ 0.000000 │ 0.000000  │  2.215754 β  │ 5D1pdQ │ 5CVM6F │ ALAN (*Owner) │     -
 6  │ 29.85k β │ 29.85k β │  τ 0.00 │ 0.000000 │ 0.000000  │  4.165723 β  │ 5H99rY │ 5Ci8ui │ ~             │     -
 2  │  3.71k β │  3.71k β │  τ 0.00 │ 0.000000 │ 0.000000  │  0.517408 β  │ 5HRHqA │ 5HGPue │ ~             │     -
    """

    entries, _ = service._parse_output(output)

    roles_by_uid = {entry.uid: entry.role for entry in entries}
    assert roles_by_uid[0] == "validator"
    assert roles_by_uid[6] == "validator"
    assert roles_by_uid[2] == "miner"

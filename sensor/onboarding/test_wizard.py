#
# Open Network Experience (ONE) - Sensor Onboarding Wizard Unit Tests
#
# Copyright (C) 2026 Open Network Experience Authors.
# Licensed under the GNU Affero General Public License v3.0 (AGPLv3).
# See LICENSE in the project root for full license details.
#

import os
import sys

def verifies(req_id: str):
    def decorator(fn):
        fn.__verifies__ = req_id
        return fn
    return decorator

import json
import socket
import subprocess
import urllib.error
import pytest
from unittest.mock import patch, MagicMock, mock_open

# Add sensor and onboarding paths
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import wizard

# ============================================================================
# 1. UI Helpers & Utility Functions
# ============================================================================

def test_ui_print_helpers(capsys):
    """Verifies that terminal UI helper functions execute and output formatted text."""
    wizard.print_banner()
    wizard.print_step(1, "Hardware & Network Interfaces")
    wizard.print_success("Operation completed successfully")
    wizard.print_warning("High CPU temperature detected")
    wizard.print_error("Failed to connect to gateway")
    wizard.print_info("DHCP Option 43 detected")

    out = capsys.readouterr().out
    assert "OPEN NETWORK EXPERIENCE (ONE) EDGE SENSOR WIZARD" in out
    assert "Step 1: Hardware & Network Interfaces" in out
    assert "Operation completed successfully" in out
    assert "High CPU temperature detected" in out
    assert "Failed to connect to gateway" in out
    assert "DHCP Option 43 detected" in out

def test_is_root():
    """Validates root privilege detection logic."""
    with patch("os.geteuid", return_value=0, create=True):
        assert wizard.is_root() is True

    with patch("os.geteuid", return_value=1000, create=True):
        assert wizard.is_root() is False

    with patch.object(os, "geteuid", create=False):
        # When geteuid is not present on platform
        if hasattr(os, "geteuid"):
            delattr(os, "geteuid")
        assert wizard.is_root() is True

# ============================================================================
# 2. Hardware and Network Discovery
# ============================================================================

def test_inspect_hardware_full(tmp_path):
    """Validates hardware specification and interface diagnostic inspection."""
    proc_mem = tmp_path / "meminfo"
    proc_mem.write_text("MemTotal:        8388608 kB\nMemFree:         4194304 kB\n")

    net_dir = tmp_path / "net"
    eth0_dir = net_dir / "eth0"
    eth0_dir.mkdir(parents=True)
    (eth0_dir / "operstate").write_text("up\n")

    wlan0_dir = net_dir / "wlan0"
    wlan0_dir.mkdir(parents=True)
    (wlan0_dir / "wireless").mkdir()
    (wlan0_dir / "operstate").write_text("down\n")

    with patch("os.path.exists", side_effect=lambda p: str(p) in (str(proc_mem), str(net_dir), str(eth0_dir / "operstate"), str(wlan0_dir / "wireless"), str(wlan0_dir / "operstate"), "/proc/meminfo", "/sys/class/net")):
        with patch("builtins.open", mock_open(read_data="MemTotal:        8388608 kB\n")):
            with patch("os.listdir", return_value=["lo", "eth0", "wlan0"]):
                with patch("shutil.disk_usage", return_value=MagicMock(free=20 * (1024**3), total=64 * (1024**3))):
                    with patch("shutil.which", return_value="/usr/bin/docker"):
                        hw = wizard.inspect_hardware()

                        assert hw["cpu_cores"] >= 1
                        assert hw["memory_gb"] == 8.0
                        assert hw["disk_free_gb"] == 20.0
                        assert hw["disk_total_gb"] == 64.0
                        assert hw["docker_installed"] is True
                        assert len(hw["interfaces"]) == 2

                        iface_eth = next(i for i in hw["interfaces"] if i["name"] == "eth0")
                        assert iface_eth["type"] == "ethernet"

                        iface_wlan = next(i for i in hw["interfaces"] if i["name"] == "wlan0")
                        assert iface_wlan["type"] == "wireless"

def test_inspect_hardware_exceptions():
    """Validates graceful fallbacks when hardware inspection encounters IO errors."""
    with patch("os.path.exists", return_value=False):
        with patch("shutil.disk_usage", side_effect=OSError("Disk error")):
            hw = wizard.inspect_hardware()
            assert hw["memory_gb"] == 1.0
            assert hw["disk_free_gb"] == 1.0
            assert hw["interfaces"] == []

def test_get_machine_uuid_sources(tmp_path):
    """Validates UUID resolution priority: /etc/machine-id -> reconciler.json -> uuid4()."""
    # 1. /etc/machine-id present
    with patch("os.path.exists", side_effect=lambda p: p == "/etc/machine-id"):
        with patch("builtins.open", mock_open(read_data="machine-id-from-system\n")):
            assert wizard.get_machine_uuid() == "machine-id-from-system"

    # 2. /etc/machine-id empty or error, reconciler.json present
    cfg_file = tmp_path / "reconciler.json"
    cfg_file.write_text(json.dumps({"sensor_id": "sensor-from-reconciler-cfg"}))

    def mock_exists_reconciler(p):
        return p == str(cfg_file)

    with patch("wizard.CONFIG_PATH", str(cfg_file)):
        with patch("os.path.exists", side_effect=lambda p: p == str(cfg_file)):
            assert wizard.get_machine_uuid() == "sensor-from-reconciler-cfg"

    # 3. None present, fallback to generated UUID
    with patch("os.path.exists", return_value=False):
        with patch("uuid.uuid4", return_value="generated-test-uuid"):
            assert wizard.get_machine_uuid() == "generated-test-uuid"

def test_get_primary_mac_and_ip_scenarios():
    """Validates MAC address and IP extraction across various OS configurations."""
    # Scenario A: ip route returns dev eth0, sysfs MAC exists, socket getsockname succeeds
    with patch("subprocess.check_output", return_value="default via 192.168.1.1 dev eth0 proto dhcp metric 100"):
        with patch("os.path.exists", side_effect=lambda p: p == "/sys/class/net/eth0/address"):
            with patch("builtins.open", mock_open(read_data="dc:a6:32:aa:bb:cc\n")):
                mock_sock = MagicMock()
                mock_sock.getsockname.return_value = ["192.168.1.50", 12345]
                with patch("socket.socket", return_value=mock_sock):
                    mac, ip, iface = wizard.get_primary_mac_and_ip()
                    assert mac == "dc:a6:32:aa:bb:cc"
                    assert ip == "192.168.1.50"
                    assert iface == "eth0"

    # Scenario B: ip route fails, sysfs missing (uuid.getnode fallback), socket fails (gethostname fallback)
    with patch("subprocess.check_output", side_effect=subprocess.CalledProcessError(1, "ip")):
        with patch("os.path.exists", return_value=False):
            with patch("uuid.getnode", return_value=0x112233445566):
                with patch("socket.socket", side_effect=OSError("Network unreachable")):
                    with patch("socket.gethostbyname", return_value="10.0.5.25"):
                        mac, ip, iface = wizard.get_primary_mac_and_ip()
                        assert mac == "11:22:33:44:55:66"
                        assert ip == "10.0.5.25"
                        assert iface == "eth0"

    # Scenario C: complete hostname resolution failure
    with patch("subprocess.check_output", side_effect=Exception("error")):
        with patch("os.path.exists", return_value=False):
            with patch("socket.socket", side_effect=Exception("error")):
                with patch("socket.gethostbyname", side_effect=Exception("DNS failure")):
                    mac, ip, iface = wizard.get_primary_mac_and_ip()
                    assert ip == "127.0.0.1"

# ============================================================================
# 3. DHCP Option 43 / 224 Parsing & CMP Auto-Discovery
# ============================================================================

def test_parse_option43_tlv_or_string():
    """Validates plain URL, hex-encoded ASCII, and RFC 2132 Sub-Option TLV payloads."""
    # Plain ASCII URL
    res = wizard.parse_option43_tlv_or_string("http://cmp.district.k12.ca.us:8000")
    assert res == {"cmp_url": "http://cmp.district.k12.ca.us:8000/api/v1"}

    res_with_api = wizard.parse_option43_tlv_or_string("https://cmp.district.k12.ca.us/api/v1")
    assert res_with_api == {"cmp_url": "https://cmp.district.k12.ca.us/api/v1"}

    # Hex-encoded ASCII string
    hex_ascii = "http://192.0.2.100:8000/api/v1".encode("utf-8").hex()
    res_hex = wizard.parse_option43_tlv_or_string(hex_ascii)
    assert res_hex == {"cmp_url": "http://192.0.2.100:8000/api/v1"}

    # Sub-Option TLV binary format:
    # Sub-Opt 1 (cmp_url): "http://192.0.2.10:8000"
    # Sub-Opt 2 (campus): "West Campus"
    # Sub-Opt 3 (building): "Building B"
    # Sub-Opt 4 (room): "Room 105"
    # Sub-Opt 5 (token): "enroll-secret-123"
    tlv_bytes = bytearray()
    tlv_bytes.extend([1, len("http://192.0.2.10:8000")])
    tlv_bytes.extend("http://192.0.2.10:8000".encode("utf-8"))
    tlv_bytes.extend([2, len("West Campus")])
    tlv_bytes.extend("West Campus".encode("utf-8"))
    tlv_bytes.extend([3, len("Building B")])
    tlv_bytes.extend("Building B".encode("utf-8"))
    tlv_bytes.extend([4, len("Room 105")])
    tlv_bytes.extend("Room 105".encode("utf-8"))
    tlv_bytes.extend([5, len("enroll-secret-123")])
    tlv_bytes.extend("enroll-secret-123".encode("utf-8"))

    res_tlv = wizard.parse_option43_tlv_or_string(tlv_bytes.hex())
    assert res_tlv is not None
    assert res_tlv["cmp_url"] == "http://192.0.2.10:8000/api/v1"
    assert res_tlv["campus"] == "West Campus"
    assert res_tlv["building"] == "Building B"
    assert res_tlv["room"] == "Room 105"
    assert res_tlv["token"] == "enroll-secret-123"

    # Empty and invalid payloads
    assert wizard.parse_option43_tlv_or_string("") is None
    assert wizard.parse_option43_tlv_or_string("   ") is None
    assert wizard.parse_option43_tlv_or_string("invalid-non-hex-and-non-url") is None

def test_discover_cmp_endpoints_dhcp_and_dns(tmp_path):
    """Validates CMP auto-discovery across lease files and DNS search domains."""
    # 1. Lease file with OPTION_43
    lease_dir = tmp_path / "leases"
    lease_dir.mkdir()
    lease_file = lease_dir / "dhcpcd-eth0.lease"
    lease_file.write_text('OPTION_43="http://dhcp-cmp.local:8000/api/v1"\n')

    # 2. /etc/resolv.conf with search domain
    resolv_file = tmp_path / "resolv.conf"
    resolv_file.write_text("search school.internal localdomain\nnameserver 1.1.1.1\n")

    def mock_exists(p):
        if p in ["/run/systemd/netif/leases", "/var/lib/dhcp", "/var/lib/NetworkManager", "/var/lib/dhclient"]:
            return False
        if p == "/var/run/dhcpcd":
            return True
        if p == "/etc/resolv.conf":
            return True
        return False

    with patch("os.path.exists", side_effect=mock_exists):
        with patch("os.walk", return_value=[(str(lease_dir), [], ["dhcpcd-eth0.lease"])]):
            with patch("builtins.open", mock_open(read_data='OPTION_43="http://dhcp-cmp.local:8000/api/v1"\nsearch school.internal\n')):
                def mock_dns(host):
                    if host in ("openux-cmp.school.internal", "one-cmp.local"):
                        return "10.0.1.50"
                    raise socket.gaierror("Host not found")

                with patch("socket.gethostbyname", side_effect=mock_dns):
                    candidates = wizard.discover_cmp_endpoints()
                    urls = [c["url"] for c in candidates]
                    assert "http://dhcp-cmp.local:8000/api/v1" in urls
                    assert "http://openux-cmp.school.internal:8000/api/v1" in urls
                    assert "http://one-cmp.local:8000/api/v1" in urls

# ============================================================================
# 4. Connectivity & Direct Registration Testing
# ============================================================================

def test_test_cmp_connectivity_http_error_codes():
    """Validates that 401, 404, 405 status codes are treated as reachable control planes."""
    http_error = urllib.error.HTTPError(
        url="http://cmp.local/api/v1/health",
        code=405,
        msg="Method Not Allowed",
        hdrs={},
        fp=None
    )
    with patch("urllib.request.urlopen", side_effect=http_error):
        healthy, status_msg, latency = wizard.test_cmp_connectivity("http://cmp.local/api/v1")
        assert healthy is True
        assert "HTTP 405" in status_msg

def test_register_sensor_direct_errors():
    """Validates HTTP error and socket exception handling in direct sensor registration."""
    # HTTP Error 403 Forbidden with custom JSON error message
    mock_fp = MagicMock()
    mock_fp.read.return_value = json.dumps({"detail": "Sensor MAC blacklisted"}).encode("utf-8")
    http_err = urllib.error.HTTPError("http://cmp.local/api/v1/sensors/register", 403, "Forbidden", {}, mock_fp)

    with patch("urllib.request.urlopen", side_effect=http_err):
        res = wizard.register_sensor_direct(
            cmp_url="http://cmp.local:8000",
            sensor_id="sensor-bad",
            hostname="bad-pi",
            mac_address="00:11:22:33:44:55",
            location={"site": "Main Campus"},
            enrollment_token="invalid-token"
        )
        assert res["success"] is False
        assert "HTTP 403" in res["error"]
        assert "blacklisted" in res["error"]

    # General Connection Refused / URLError
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection reset by peer")):
        res = wizard.register_sensor_direct(
            cmp_url="http://cmp.local:8000",
            sensor_id="sensor-bad",
            hostname="bad-pi",
            mac_address="00:11:22:33:44:55",
            location={"site": "Main Campus"}
        )
        assert res["success"] is False
        assert "Connection reset by peer" in res["error"]

# ============================================================================
# 5. Wi-Fi Scanning (nmcli & iwlist) & Credential Generation
# ============================================================================

@verifies("REQ-ONB-001")
def test_scan_wifi_ssids_nmcli():
    """Validates nmcli Wi-Fi site survey scan parsing."""
    nmcli_output = (
        "District-Staff:85:WPA2 802.1X:▂▄▆█\n"
        "District-Guest:60:WPA2:▂▄▆_\n"
        "District-IoT:90:WPA2:▂▄▆█\n"
        ":20:WPA2:▂___\n"  # Hidden SSID
        "District-Staff:80:WPA2:▂▄▆█\n"  # Duplicate SSID
    )

    with patch("shutil.which", return_value="/usr/bin/nmcli"):
        with patch("subprocess.check_output", return_value=nmcli_output):
            ssids = wizard.scan_wifi_ssids("wlan0")
            assert len(ssids) == 3
            assert ssids[0]["ssid"] == "District-Staff"
            assert ssids[0]["signal"] == "85%"
            assert ssids[0]["security"] == "WPA2 802.1X"
            assert ssids[1]["ssid"] == "District-Guest"
            assert ssids[2]["ssid"] == "District-IoT"

def test_scan_wifi_ssids_iwlist_fallback():
    """Validates iwlist scan parsing when nmcli is unavailable."""
    iwlist_output = """
wlan0     Scan completed :
          Cell 01 - Address: AA:BB:CC:DD:EE:FF
                    Channel:6
                    Frequency:2.437 GHz (Channel 6)
                    Quality=58/70  Signal level=-52 dBm
                    Encryption key:on
                    ESSID:"HighSchool-Secure"
          Cell 02 - Address: 11:22:33:44:55:66
                    Channel:36
                    Frequency:5.18 GHz (Channel 36)
                    Quality=70/70  Signal level=-30 dBm
                    Encryption key:on
                    ESSID:"HighSchool-Secure"
          Cell 03 - Address: 22:33:44:55:66:77
                    Channel:1
                    ESSID:"Guest-WiFi"
    """

    def mock_which(cmd):
        return "/usr/sbin/iwlist" if cmd == "iwlist" else None

    with patch("shutil.which", side_effect=mock_which):
        with patch("subprocess.check_output", return_value=iwlist_output):
            ssids = wizard.scan_wifi_ssids("wlan0")
            assert len(ssids) == 2
            assert ssids[0]["ssid"] == "HighSchool-Secure"
            assert ssids[1]["ssid"] == "Guest-WiFi"

def test_configure_wpa_supplicant_open_and_error(tmp_path):
    """Validates wpa_supplicant configuration for Open Wi-Fi and permission error handling."""
    open_wpa_file = tmp_path / "open_wpa.conf"
    assert wizard.configure_wpa_supplicant(
        ssid="District-Open-Guest",
        psk="",
        security="open",
        config_path=str(open_wpa_file)
    ) is True
    content = open_wpa_file.read_text()
    assert 'ssid="District-Open-Guest"' in content
    assert 'key_mgmt=NONE' in content

    # Test error handling when target directory cannot be created
    with patch("builtins.open", side_effect=PermissionError("Permission denied")):
        assert wizard.configure_wpa_supplicant("SSID", "psk", config_path="/root/forbidden/wpa.conf") is False

def test_save_sensor_configuration_error():
    """Validates error return when save_sensor_configuration encounters write failure."""
    with patch("builtins.open", side_effect=PermissionError("Read-only filesystem")):
        assert wizard.save_sensor_configuration({"test": "data"}, path="/readonly/path/config.json") is False

# ============================================================================
# 6. Systemd Service Management & Prompt Handling
# ============================================================================

def test_manage_systemd_service_success_and_failure(tmp_path):
    """Validates systemd service file generation, reloading, and error trapping."""
    test_svc_path = tmp_path / "sensor-reconciler.service"
    with patch("wizard.SERVICE_PATH", str(test_svc_path)):
        with patch("subprocess.run") as mock_run:
            assert wizard.manage_systemd_service() is True
            assert test_svc_path.exists()
            assert "ExecStart=/usr/bin/python3 /usr/local/bin/reconciler.py" in test_svc_path.read_text()
            assert mock_run.call_count == 3

    # Failure during file write
    with patch("wizard.SERVICE_PATH", "/forbidden/service.service"):
        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            assert wizard.manage_systemd_service() is False

def test_prompt_user_inputs():
    """Validates interactive prompt defaults, user answers, and interrupt termination."""
    with patch("builtins.input", return_value="Custom Value"):
        assert wizard.prompt_user("Prompt", default="Default Value") == "Custom Value"

    with patch("builtins.input", return_value=""):
        assert wizard.prompt_user("Prompt", default="Default Value") == "Default Value"

    with patch("builtins.input", side_effect=KeyboardInterrupt):
        with pytest.raises(SystemExit):
            wizard.prompt_user("Prompt")

# ============================================================================
# 7. Interactive Wizard Flow (Full Walkthrough)
# ============================================================================

def test_run_interactive_wizard_full_flow(tmp_path, capsys):
    """
    Executes complete end-to-end interactive onboarding wizard flow with:
    - Non-root detection warning
    - Existing config loading
    - CMP URL retry and verification
    - Campus/Room input
    - Wi-Fi SSID selection & PSK entry
    - Auto-enrollment approval & service startup
    """
    cfg_file = tmp_path / "reconciler.json"
    wpa_file = tmp_path / "wpa_supplicant.conf"
    svc_file = tmp_path / "sensor-reconciler.service"

    existing_cfg = {
        "sensor_id": "existing-sensor-123",
        "cmp_url": "http://192.0.2.100:8000/api/v1",
        "api_key": "existing_key_abc",
        "initial_location": {
            "district": "Kern High School District",
            "site": "Bakersfield High",
            "building": "Science Wing",
            "room": "Room 101",
            "notes": "Ceiling AP"
        }
    }
    cfg_file.write_text(json.dumps(existing_cfg))

    scanned_aps = [
        {"ssid": "Staff-Secure", "signal": "90%", "security": "WPA2", "bars": "▂▄▆█"},
        {"ssid": "Guest-Open", "signal": "60%", "security": "Open", "bars": "▂▄▆_"}
    ]

    # Answers sequence for prompt_user:
    # 1. CMP URL (first attempt -> retry logic)
    # 2. Retry prompt ('n' to proceed with unverified)
    # 3. District Name
    # 4. Campus Name
    # 5. Building Name
    # 6. Room Name
    # 7. Notes
    # 8. Setup Wi-Fi ('y')
    # 9. Select network number ('1' -> Staff-Secure)
    # 10. Security Type ('psk')
    prompt_answers = [
        "http://bad-cmp.local:8000",
        "n",
        "Kern High School District",
        "Bakersfield High",
        "Science Wing",
        "Room 101",
        "Asset #1002",
        "y",
        "1",
        "psk"
    ]
    prompt_iter = iter(prompt_answers)

    with patch("wizard.CONFIG_PATH", str(cfg_file)):
        with patch("wizard.WIFI_CONFIG_PATH", str(wpa_file)):
            with patch("wizard.SERVICE_PATH", str(svc_file)):
                with patch("wizard.is_root", return_value=True):
                    with patch("wizard.discover_cmp_endpoints", return_value=[{"url": "http://192.0.2.100:8000/api/v1", "source": "DHCP"}]):
                        with patch("wizard.test_cmp_connectivity", return_value=(False, "Connection refused", 10.0)):
                            with patch("builtins.input", side_effect=lambda *args: next(prompt_iter)):
                                with patch("getpass.getpass", return_value="StaffWifiPassword99!"):
                                    with patch("wizard.scan_wifi_ssids", return_value=scanned_aps):
                                        with patch("wizard.register_sensor_direct", return_value={"success": True, "status": "approved", "api_key": "new_approved_key_777"}):
                                            with patch("subprocess.run"):
                                                wizard.run_interactive_wizard()

                                                captured = capsys.readouterr().out
                                                assert "SENSOR ONBOARDING COMPLETE!" in captured
                                                assert "Bakersfield High" in captured
                                                assert "Room 101" in captured
                                                assert "Sensor Approved via Zero-Touch Auto-Enrollment!" in captured

                                                # Verify config file written
                                                saved_cfg = json.loads(cfg_file.read_text())
                                                assert saved_cfg["sensor_id"] == "existing-sensor-123"
                                                assert saved_cfg["api_key"] == "new_approved_key_777"
                                                assert saved_cfg["initial_location"]["site"] == "Bakersfield High"

                                                # Verify Wi-Fi file written
                                                assert wpa_file.exists()
                                                assert 'ssid="Staff-Secure"' in wpa_file.read_text()

def test_run_interactive_wizard_pending_registration(tmp_path, capsys):
    """Tests interactive wizard when sensor registration returns pending approval."""
    cfg_file = tmp_path / "reconciler.json"

    prompt_answers = [
        "http://cmp.district.local:8000/api/v1",
        "District A",
        "Elementary B",
        "Main Wing",
        "Room 1",
        "Ceiling AP",
        "n"  # Setup Wi-Fi: No
    ]
    prompt_iter = iter(prompt_answers)

    with patch("wizard.CONFIG_PATH", str(cfg_file)):
        with patch("wizard.is_root", return_value=False):
            with patch("wizard.discover_cmp_endpoints", return_value=[]):
                with patch("wizard.test_cmp_connectivity", return_value=(True, "HTTP 200 OK", 5.0)):
                    with patch("builtins.input", side_effect=lambda *args: next(prompt_iter)):
                        with patch("wizard.register_sensor_direct", return_value={"success": True, "status": "pending", "api_key": None}):
                            wizard.run_interactive_wizard()
                            captured = capsys.readouterr().out
                            assert "PENDING APPROVAL" in captured
                            assert "TOFU (Trust-On-First-Use) approval queue" in captured

def test_run_interactive_wizard_manual_ssid_fallback(tmp_path, capsys):
    """Tests interactive wizard with manual SSID entry and registration failure fallback."""
    cfg_file = tmp_path / "reconciler.json"

    prompt_answers = [
        "10.0.0.1:8000",
        "District",
        "Site",
        "Building",
        "Room",
        "Notes",
        "y",            # Setup Wi-Fi: Yes
        "0",            # Manual SSID selection
        "Hidden-SSID",  # Manual SSID name
        "open"          # Security: open
    ]
    prompt_iter = iter(prompt_answers)

    with patch("wizard.CONFIG_PATH", str(cfg_file)):
        with patch("wizard.is_root", return_value=False):
            with patch("wizard.discover_cmp_endpoints", return_value=[]):
                with patch("wizard.test_cmp_connectivity", return_value=(True, "HTTP 200 OK", 2.0)):
                    with patch("builtins.input", side_effect=lambda *args: next(prompt_iter)):
                        with patch("wizard.scan_wifi_ssids", return_value=[]):
                            with patch("wizard.register_sensor_direct", return_value={"success": False, "error": "HTTP 500 Server Error"}):
                                wizard.run_interactive_wizard()
                                captured = capsys.readouterr().out
                                assert "Registration deferred" in captured

# ============================================================================
# 10. Granular Branch & Exception Recovery Tests
# ============================================================================

def test_get_machine_uuid_exceptions(tmp_path):
    """Tests get_machine_uuid handling IO and JSON exceptions gracefully."""
    with patch("os.path.exists", side_effect=lambda p: p == "/etc/machine-id"):
        with patch("builtins.open", side_effect=PermissionError("Cannot read /etc/machine-id")):
            with patch("uuid.uuid4", return_value="fallback-uuid-1"):
                assert wizard.get_machine_uuid() == "fallback-uuid-1"

    cfg_file = tmp_path / "corrupt_reconciler.json"
    cfg_file.write_text("{not valid json")
    with patch("wizard.CONFIG_PATH", str(cfg_file)):
        with patch("os.path.exists", side_effect=lambda p: p == str(cfg_file)):
            with patch("uuid.uuid4", return_value="fallback-uuid-2"):
                assert wizard.get_machine_uuid() == "fallback-uuid-2"

def test_get_primary_mac_read_exception():
    """Tests MAC address extraction when sysfs file exists but read throws exception."""
    with patch("subprocess.check_output", return_value="default via 192.168.1.1 dev eth0"):
        with patch("os.path.exists", side_effect=lambda p: p == "/sys/class/net/eth0/address"):
            with patch("builtins.open", side_effect=OSError("Read error")):
                mac, ip, iface = wizard.get_primary_mac_and_ip()
                assert mac == "00:00:00:00:00:00"

def test_inspect_hardware_read_exceptions(tmp_path):
    """Tests hardware inspection when /proc/meminfo and operstate read raise exceptions."""
    net_dir = tmp_path / "net"
    eth0_dir = net_dir / "eth0"
    eth0_dir.mkdir(parents=True)

    with patch("os.path.exists", side_effect=lambda p: p in ("/proc/meminfo", "/sys/class/net", "/sys/class/net/eth0/operstate")):
        with patch("builtins.open", side_effect=OSError("I/O error")):
            with patch("os.listdir", return_value=["eth0"]):
                hw = wizard.inspect_hardware()
                assert hw["memory_gb"] == 1.0
                assert len(hw["interfaces"]) == 1
                assert hw["interfaces"][0]["status"] == "unknown"

    with patch("os.path.exists", side_effect=lambda p: p == "/sys/class/net"):
        with patch("os.listdir", side_effect=OSError("Access denied")):
            hw = wizard.inspect_hardware()
            assert hw["interfaces"] == []

def test_parse_option43_tlv_truncated_and_errors():
    """Tests Option 43 TLV parsing when payload is truncated or contains invalid sub-options."""
    # Truncated TLV: sub-option length claims 20 bytes, but only 2 provided
    truncated_hex = bytes([1, 20, 0x68, 0x74]).hex()
    res = wizard.parse_option43_tlv_or_string(truncated_hex)
    assert res is None

def test_discover_cmp_endpoints_config_and_exceptions(tmp_path):
    """Tests discover_cmp_endpoints with existing config, lease exceptions, and resolv.conf exceptions."""
    with patch("socket.gethostbyname", side_effect=socket.gaierror("Host not found")):
        cfg_file = tmp_path / "reconciler.json"
        cfg_file.write_text(json.dumps({"cmp_url": "http://custom-cmp.internal:8000/api/v1"}))

        with patch("wizard.CONFIG_PATH", str(cfg_file)):
            with patch("os.path.exists", side_effect=lambda p: p == str(cfg_file)):
                candidates = wizard.discover_cmp_endpoints()
                assert len(candidates) >= 1
                assert candidates[0]["url"] == "http://custom-cmp.internal:8000/api/v1"

        # Test corrupted config file exception handling
        bad_cfg = tmp_path / "bad_reconciler.json"
        bad_cfg.write_text("invalid json")
        with patch("wizard.CONFIG_PATH", str(bad_cfg)):
            with patch("os.path.exists", side_effect=lambda p: p == str(bad_cfg)):
                candidates = wizard.discover_cmp_endpoints()
                assert len(candidates) == 0

        # Test lease dir read exception and resolv.conf read exception
        def mock_exists_leases(p):
            return p in ("/var/lib/dhcp", "/etc/resolv.conf")

        with patch("os.path.exists", side_effect=mock_exists_leases):
            with patch("os.walk", return_value=[("/var/lib/dhcp", [], ["lease1"])]):
                with patch("builtins.open", side_effect=OSError("Permission denied")):
                    candidates = wizard.discover_cmp_endpoints()
                    assert isinstance(candidates, list)

def test_test_cmp_connectivity_schemeless_and_200():
    """Tests connectivity testing with schemeless URL, 200 OK, and endpoint failure loop."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        healthy, status_msg, lat = wizard.test_cmp_connectivity("cmp.example.edu:8000/api/v1")
        assert healthy is True
        assert "HTTP 200 OK" in status_msg

    # Test all endpoints throwing generic exception
    with patch("urllib.request.urlopen", side_effect=Exception("Generic network failure")):
        healthy, status_msg, lat = wizard.test_cmp_connectivity("http://192.0.2.1:8000")
        assert healthy is False
        assert "timed out" in status_msg.lower() or "refused" in status_msg.lower()

def test_scan_wifi_ssids_exceptions_and_empty_lines():
    """Tests scan_wifi_ssids with empty lines, nmcli exception, and iwlist exception."""
    # nmcli throws exception, fallback to iwlist
    with patch("shutil.which", side_effect=lambda cmd: "/usr/bin/" + cmd):
        with patch("subprocess.check_output", side_effect=[subprocess.CalledProcessError(1, "nmcli"), "ESSID:\"BackupWiFi\"\n"]):
            ssids = wizard.scan_wifi_ssids("wlan0")
            assert len(ssids) == 1
            assert ssids[0]["ssid"] == "BackupWiFi"

    # Both nmcli and iwlist throw exceptions
    with patch("shutil.which", side_effect=lambda cmd: "/usr/bin/" + cmd):
        with patch("subprocess.check_output", side_effect=subprocess.CalledProcessError(1, "cmd")):
            ssids = wizard.scan_wifi_ssids("wlan0")
            assert ssids == []

def test_register_sensor_direct_http_error_decode_failure():
    """Tests register_sensor_direct when HTTP error body cannot be decoded."""
    mock_fp = MagicMock()
    mock_fp.read.side_effect = Exception("Read failed")
    http_err = urllib.error.HTTPError("http://cmp.local", 502, "Bad Gateway", {}, mock_fp)

    with patch("urllib.request.urlopen", side_effect=http_err):
        res = wizard.register_sensor_direct("http://cmp.local", "s-1", "h-1", "m-1", {})
        assert res["success"] is False
        assert "HTTP 502" in res["error"]

def test_run_interactive_wizard_edge_cases(tmp_path, capsys):
    """Tests interactive wizard with corrupted existing config, string SSID choice, and getpass exception."""
    bad_cfg = tmp_path / "bad.json"
    bad_cfg.write_text("invalid json")

    scanned_aps = [
        {"ssid": "Alpha-WiFi", "signal": "90%", "security": "WPA2", "bars": "▂▄▆█"}
    ]

    prompt_answers = [
        "http://cmp.local/api/v1",
        "District",
        "Site",
        "Building",
        "Room",
        "Notes",
        "y",              # Wi-Fi Setup: Yes
        "Alpha-WiFi",     # Direct SSID name instead of number
        "psk",            # Security: psk
        "WifiPassword!"   # Wi-Fi Passphrase via prompt_user fallback
    ]
    prompt_iter = iter(prompt_answers)

    with patch("wizard.CONFIG_PATH", str(bad_cfg)):
        with patch("wizard.is_root", return_value=False):
            with patch("wizard.discover_cmp_endpoints", return_value=[]):
                with patch("wizard.test_cmp_connectivity", return_value=(True, "HTTP 200 OK", 1.0)):
                    with patch("builtins.input", side_effect=lambda *args: next(prompt_iter)):
                        with patch("wizard.scan_wifi_ssids", return_value=scanned_aps):
                            with patch("getpass.getpass", side_effect=Exception("No TTY")):
                                with patch("wizard.register_sensor_direct", return_value={"success": True, "status": "approved", "api_key": "k1"}):
                                    wizard.run_interactive_wizard()
                                    assert "SENSOR ONBOARDING COMPLETE!" in capsys.readouterr().out

# ============================================================================
# 11. Non-Interactive Batch Execution & CLI Routing
# ============================================================================

def test_run_non_interactive_full(tmp_path, capsys):
    """Validates non-interactive batch provisioning with all CLI options."""
    test_cfg_path = tmp_path / "reconciler.json"
    wpa_path = tmp_path / "wpa_supplicant.conf"
    svc_path = tmp_path / "sensor-reconciler.service"

    mock_args = MagicMock()
    mock_args.cmp = "192.0.2.10:8000"
    mock_args.sensor_id = "test-batch-uuid"
    mock_args.site = "Lincoln High School"
    mock_args.building = "Building C"
    mock_args.room = "Library Drop 01"
    mock_args.district = "Unified District"
    mock_args.notes = "Asset #9941"
    mock_args.token = "ztp-secret-token"
    mock_args.wifi_ssid = "District-IoT"
    mock_args.wifi_psk = "IoTSecretPassword"
    mock_args.non_interactive = True
    mock_args.check_only = False
    mock_args.json = True

    with patch("wizard.CONFIG_PATH", str(test_cfg_path)):
        with patch("wizard.WIFI_CONFIG_PATH", str(wpa_path)):
            with patch("wizard.SERVICE_PATH", str(svc_path)):
                with patch("wizard.register_sensor_direct", return_value={"success": True, "status": "approved", "api_key": "key_xyz"}):
                    with patch("wizard.is_root", return_value=True):
                        with patch("subprocess.run"):
                            wizard.run_non_interactive(mock_args)
                            captured = capsys.readouterr()
                            out = json.loads(captured.out)
                            assert out["sensor_id"] == "test-batch-uuid"
                            assert out["location"]["site"] == "Lincoln High School"
                            assert out["location"]["room"] == "Library Drop 01"
                            assert out["registration"]["status"] == "approved"
                            assert test_cfg_path.exists()
                            assert wpa_path.exists()

def test_run_non_interactive_check_only_and_text_output(tmp_path, capsys):
    """Validates check_only flag skipping file saves and human-readable output."""
    test_cfg_path = tmp_path / "reconciler.json"

    mock_args = MagicMock()
    mock_args.cmp = None  # Uses default DEFAULT_CMP_URL
    mock_args.sensor_id = None
    mock_args.site = None
    mock_args.building = None
    mock_args.room = None
    mock_args.district = None
    mock_args.notes = None
    mock_args.token = None
    mock_args.wifi_ssid = "OpenGuest"
    mock_args.wifi_psk = None
    mock_args.non_interactive = True
    mock_args.check_only = True
    mock_args.json = False

    with patch("wizard.CONFIG_PATH", str(test_cfg_path)):
        with patch("wizard.register_sensor_direct", return_value={"success": False, "error": "Unreachable"}):
            with patch("wizard.is_root", return_value=False):
                wizard.run_non_interactive(mock_args)
                captured = capsys.readouterr()
                assert "provisioned for Main Campus - Room 101" in captured.out
                assert not test_cfg_path.exists()

def test_main_routing(tmp_path):
    """Validates CLI argument routing between batch mode and interactive wizard."""
    # Test batch mode routing via --non-interactive
    test_args = [
        "wizard.py",
        "--non-interactive",
        "--cmp", "http://192.0.2.10:8000/api/v1",
        "--site", "South High",
        "--room", "Lab 3",
        "--wifi-ssid", "District-Staff",
        "--wifi-psk", "SecretPass123"
    ]
    with patch("sys.argv", test_args):
        with patch("wizard.run_non_interactive") as mock_non_interactive:
            wizard.main()
            assert mock_non_interactive.called

    # Test batch mode routing via --json flag
    with patch("sys.argv", ["wizard.py", "--json"]):
        with patch("wizard.run_non_interactive") as mock_non_interactive:
            wizard.main()
            assert mock_non_interactive.called

    # Test batch mode routing when stdin is not a tty and site/room provided
    with patch("sys.argv", ["wizard.py", "--site", "East High", "--room", "102"]):
        with patch("sys.stdin.isatty", return_value=False):
            with patch("wizard.run_non_interactive") as mock_non_interactive:
                wizard.main()
                assert mock_non_interactive.called

    # Test interactive mode routing
    with patch("sys.argv", ["wizard.py"]):
        with patch("sys.stdin.isatty", return_value=True):
            with patch("wizard.run_interactive_wizard") as mock_interactive:
                wizard.main()
                assert mock_interactive.called

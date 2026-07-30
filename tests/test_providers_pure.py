"""Unit tests for the PURE/deterministic helpers in providers.py: URL/user
normalization, path builders, tag/value formatting. No network, no ctx."""
from __future__ import annotations

import pytest

import providers as p


# ── _normalize_base_url ──────────────────────────────────────────────

def test_normalize_base_url_adds_scheme_and_port():
    assert p._normalize_base_url("pve.example.com") == "https://pve.example.com:8006"


def test_normalize_base_url_keeps_explicit_port():
    assert p._normalize_base_url("https://pve.example.com:9006") == "https://pve.example.com:9006"


def test_normalize_base_url_keeps_http_scheme():
    assert p._normalize_base_url("http://10.0.0.5:8006") == "http://10.0.0.5:8006"


def test_normalize_base_url_rejects_empty():
    with pytest.raises(p.ProxmoxError):
        p._normalize_base_url("")


def test_normalize_base_url_rejects_path_suffix():
    with pytest.raises(p.ProxmoxError):
        p._normalize_base_url("https://pve.example.com:8006/api2/json")


def test_normalize_base_url_rejects_query_string():
    with pytest.raises(p.ProxmoxError):
        p._normalize_base_url("https://pve.example.com:8006?x=1")


# ── _normalize_username_and_realm ────────────────────────────────────

def test_normalize_username_plain_with_realm_field():
    name, user_at_realm, realm = p._normalize_username_and_realm("root", "pam")
    assert (name, user_at_realm, realm) == ("root", "root@pam", "pam")


def test_normalize_username_already_has_realm():
    name, user_at_realm, realm = p._normalize_username_and_realm("root@pve", "pam")
    assert (name, user_at_realm, realm) == ("root", "root@pve", "pve")


def test_normalize_username_rejects_token_bang():
    with pytest.raises(p.ProxmoxError):
        p._normalize_username_and_realm("root@pam!imperal-ext", "pam")


def test_normalize_username_rejects_empty():
    with pytest.raises(p.ProxmoxError):
        p._normalize_username_and_realm("", "pam")


def test_normalize_username_defaults_realm_to_pam_when_blank():
    # realm="" is falsy -> `(realm or "pam")` -- the missing-realm branch
    # is defense-in-depth dead code in practice; this documents the REAL
    # behavior: blank realm silently defaults to pam, never raises.
    name, user_at_realm, realm = p._normalize_username_and_realm("root", "")
    assert (name, user_at_realm, realm) == ("root", "root@pam", "pam")


# ── masked_token_preview / auth_input_examples ───────────────────────

def test_masked_token_preview_shape():
    preview = p.masked_token_preview("root@pam", "imperal-ext")
    assert preview.startswith("PVEAPIToken=")
    assert "root@pam" in preview
    assert "imperal-ext" in preview
    assert preview.endswith("***")


def test_masked_token_preview_falls_back_on_blank():
    preview = p.masked_token_preview("", "")
    assert "<api_user>@<realm>" in preview
    assert "<token_name>" in preview


def test_auth_input_examples_mentions_expected_fields():
    examples = p.auth_input_examples("root@pam", "imperal-ext")
    joined = " ".join(examples)
    assert "api_user" in joined and "token_name" in joined


# ── guest_path / node_storage_path ───────────────────────────────────

def test_guest_path_qemu():
    assert p.guest_path("qemu", "node1", 105) == "/nodes/node1/qemu/105"


def test_guest_path_lxc():
    assert p.guest_path("lxc", "node2", 200) == "/nodes/node2/lxc/200"


def test_node_storage_path_no_storage():
    assert p.node_storage_path("node1") == "/nodes/node1/storage"


def test_node_storage_path_with_storage():
    assert p.node_storage_path("node1", "local-zfs") == "/nodes/node1/storage/local-zfs"


# ── ensure_guest_type_for_create / bool_to_proxmox_flag ──────────────

def test_ensure_guest_type_for_create_accepts_qemu_and_lxc():
    assert p.ensure_guest_type_for_create("qemu") == "qemu"
    assert p.ensure_guest_type_for_create("lxc") == "lxc"


def test_ensure_guest_type_for_create_rejects_other():
    with pytest.raises(p.ProxmoxError):
        p.ensure_guest_type_for_create("docker")


def test_bool_to_proxmox_flag_true_false_none():
    assert p.bool_to_proxmox_flag(True) == 1
    assert p.bool_to_proxmox_flag(False) == 0
    assert p.bool_to_proxmox_flag(None) is None


# ── ensure_positive_int ──────────────────────────────────────────────

def test_ensure_positive_int_passes_through_positive():
    assert p.ensure_positive_int(5, "cores") == 5


def test_ensure_positive_int_none_passthrough():
    assert p.ensure_positive_int(None, "cores") is None


def test_ensure_positive_int_rejects_zero_or_negative():
    with pytest.raises(p.ProxmoxError):
        p.ensure_positive_int(0, "cores")
    with pytest.raises(p.ProxmoxError):
        p.ensure_positive_int(-1, "cores")


# ── normalize_tag_string ─────────────────────────────────────────────

def test_normalize_tag_string_basic():
    assert p.normalize_tag_string("a, b ,c") == "a;b;c"


def test_normalize_tag_string_empty():
    assert p.normalize_tag_string("") == ""


# ── build_qemu_net0 / build_lxc_net0 ─────────────────────────────────

def test_build_qemu_net0_no_vlan():
    net0 = p.build_qemu_net0("virtio", "vmbr0")
    assert "virtio" in net0 and "bridge=vmbr0" in net0
    assert "tag=" not in net0


def test_build_qemu_net0_with_vlan():
    net0 = p.build_qemu_net0("virtio", "vmbr0", vlan_tag=42)
    assert "tag=42" in net0


def test_build_lxc_net0_dhcp_default():
    net0 = p.build_lxc_net0("vmbr0")
    assert "bridge=vmbr0" in net0
    assert "ip=dhcp" in net0


def test_build_lxc_net0_with_vlan_and_name():
    net0 = p.build_lxc_net0("vmbr0", ip_config="192.168.1.5/24", name="eth1", vlan_tag=10)
    assert "name=eth1" in net0
    assert "ip=192.168.1.5/24" in net0
    assert "tag=10" in net0


# ── build_scsi_disk_value / build_rootfs_value ───────────────────────

def test_build_scsi_disk_value_basic():
    val = p.build_scsi_disk_value("local-lvm", 32)
    assert val.startswith("local-lvm:32")


def test_build_rootfs_value_basic():
    val = p.build_rootfs_value("local-zfs", 8)
    assert val.startswith("local-zfs:8")


# ── parse_volume_reference ────────────────────────────────────────────

def test_parse_volume_reference_passthrough_storage_colon_size():
    assert p.parse_volume_reference("local-lvm:32", field_name="disk") == "local-lvm:32"


def test_parse_volume_reference_rejects_blank():
    with pytest.raises(p.ProxmoxError):
        p.parse_volume_reference("", field_name="disk")

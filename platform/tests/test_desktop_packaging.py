import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_desktop_packaging_manifest_captures_issue_requirements():
    manifest = json.loads((ROOT / "packaging" / "app-shell.json").read_text(encoding="utf-8"))

    assert manifest["enterprise_default"] == "browser_web_app"
    assert manifest["platforms"]["managed_web"] == ["browser"]
    assert manifest["platforms"]["first_class"] == ["windows", "linux"]
    assert manifest["platforms"]["future"] == ["macos"]
    assert "Preferred enterprise deployment" in manifest["serviceability"]["browser_web_app"]
    assert "Optional local/private packaging layer" in manifest["serviceability"]["desktop_shell"]
    assert manifest["clickable_entry_points"]["required"] is True
    assert "approved Blacklight web URL" in manifest["clickable_entry_points"]["managed_web"]
    assert "open /console" in manifest["clickable_entry_points"]["local_shell"]
    assert "Click Blacklight Studio" in manifest["clickable_entry_points"]["user_promise"]
    assert manifest["icons"]["app"] == (
        "packaging/assets/blacklight-studio-icon-clean-square-hires.png"
    )
    assert (
        manifest["icons"]["installer"]
        == "packaging/assets/blacklight-studio-icon-flashlight-ring-clean-square-hires.png"
    )
    assert (ROOT / manifest["icons"]["app"]).is_file()
    assert (ROOT / manifest["icons"]["installer"]).is_file()
    assert manifest["installer"]["requires_admin_for_local_model_setup"] is True
    assert manifest["installer"]["local_model_setup_can_be_skipped"] is True
    assert manifest["installer"]["provider_key_bypass_supported"] is True
    assert "administrator permissions" in manifest["installer"]["admin_permission_message"]
    assert {mode["id"] for mode in manifest["first_run_modes"]} == {
        "local_model",
        "hosted_provider",
        "demo",
    }


def test_desktop_packaging_doc_explains_install_and_bypass_paths():
    text = (ROOT / "docs" / "desktop-packaging.md").read_text(encoding="utf-8")

    assert "enterprise default should be a browser web app" in text
    assert "desktop shell should be an optional local/private packaging layer" in text
    assert "A user should be able to click a Blacklight Studio application icon" in text
    assert "managed Blacklight web URL" in text
    assert "Windows and Linux" in text
    assert "macOS" in text
    assert "packaging/assets/blacklight-studio-icon-clean-square-hires.png" in text
    assert "packaging/assets/blacklight-studio-icon-flashlight-ring-clean-square-hires.png" in text
    assert "administrator permissions" in text
    assert "Skip local model setup" in text
    assert "hosted provider key" in text

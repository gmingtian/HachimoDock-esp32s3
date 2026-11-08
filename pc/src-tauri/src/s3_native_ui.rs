//! Trusted, device-specific artwork substitution after canonical package validation.
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::{
    fs,
    io::Read,
    path::{Component, Path},
};

const INVENTORY: &[u8] = include_bytes!("../../../firmware/assets/s3-landscape-ui/inventory.json");
const JSON_LIMIT: usize = 1024 * 1024;
const SOURCE_LIMIT: usize = 8 * 1024 * 1024;
const IMAGE_LIMIT: usize = 100_000;
const IMAGE_TOTAL_LIMIT: usize = 128 * 1024;

#[derive(Debug)]
pub struct NativeComponent {
    pub widget_bytes: Vec<u8>,
    pub sprites: Vec<(String, Vec<u8>)>,
}

/// S3 firmware and its client resources use the native 320×240 artwork.
pub fn uses_native_ui(runtime: &str) -> bool {
    runtime == "esp-s3"
}

/// Only byte-identical canonical source packages qualify for artwork substitution.
/// `root` is a separately installed resource directory, never a frontend package path.
pub fn prepare_native_component(
    root: &Path,
    id: &str,
    original_package: &Path,
) -> Result<Option<NativeComponent>, String> {
    safe_name(id)?;
    let inventory: Value = serde_json::from_slice(INVENTORY).map_err(|e| e.to_string())?;
    if !inventory["components"]
        .as_array()
        .is_some_and(|ids| ids.iter().any(|v| v.as_str() == Some(id)))
    {
        return Ok(None);
    }
    let sources = inventory["sources"]
        .as_object()
        .ok_or("missing native source inventory")?;
    let prefix = format!("pc/builtin-clawpkgs/{id}/");
    // Check original identity before consulting native resources. A third-party package
    // that reuses a builtin ID must retain its own runtime and images.
    for required in ["runtime/widget.json", "buttons.json", "component.json"] {
        if !sources.contains_key(&format!("{prefix}{required}")) {
            return Err("incomplete canonical source inventory".into());
        }
    }
    for (path, expected) in sources {
        if let Some(relative) = path.strip_prefix(&prefix) {
            let Ok(bytes) = read_bounded(original_package, relative, SOURCE_LIMIT) else {
                return Ok(None);
            };
            if expected.as_str() != Some(digest(&bytes).as_str()) {
                return Ok(None);
            }
        }
    }
    let original_bytes = read_bounded(original_package, "runtime/widget.json", JSON_LIMIT)?;
    let original: Value = serde_json::from_slice(&original_bytes).map_err(|e| e.to_string())?;
    for im in original["surface"]["images"]
        .as_array()
        .into_iter()
        .flatten()
    {
        let asset = image_asset(im)?;
        if !sources.contains_key(&format!("{prefix}{asset}")) {
            return Ok(None);
        }
    }

    let installed_inventory = read_bounded(root, "inventory.json", JSON_LIMIT)?;
    if installed_inventory != INVENTORY {
        return Err("native UI inventory does not match this client release".into());
    }
    let package = format!("packages/{id}");
    let widget_bytes = read_verified(
        root,
        &inventory,
        &format!("{package}/runtime/widget.json"),
        JSON_LIMIT,
    )?;
    let widget: Value = serde_json::from_slice(&widget_bytes).map_err(|e| e.to_string())?;
    ensure_only_image_dimensions_changed(&original, &widget)?;
    for relative in ["buttons.json", "component.json"] {
        let native = read_verified(
            root,
            &inventory,
            &format!("{package}/{relative}"),
            JSON_LIMIT,
        )?;
        if native != read_bounded(original_package, relative, JSON_LIMIT)? {
            return Err(format!("native UI changed canonical {relative}"));
        }
    }
    let images = widget["surface"]["images"].as_array();
    if images.is_some_and(|images| images.len() > 4) {
        return Err("native UI exceeds four images".into());
    }
    let mut sprites = Vec::new();
    let mut total = 0;
    if let Some(images) = images.filter(|images| !images.is_empty()) {
        let index_bytes = read_verified(
            root,
            &inventory,
            &format!("surfaces/{id}/index.json"),
            JSON_LIMIT,
        )?;
        let index: Value = serde_json::from_slice(&index_bytes).map_err(|e| e.to_string())?;
        if index.as_object().map(|v| v.len()) != Some(images.len()) {
            return Err("native UI image index mismatch".into());
        }
        let mut ids = std::collections::HashSet::new();
        for im in images {
            let image_id = im["id"].as_str().ok_or("missing native image ID")?;
            safe_name(image_id)?;
            if !ids.insert(image_id) {
                return Err("duplicate native image ID".into());
            }
            let asset = image_asset(im)?;
            let source = read_verified(
                root,
                &inventory,
                &format!("{package}/{asset}"),
                SOURCE_LIMIT,
            )?;
            let encoded = read_verified(
                root,
                &inventory,
                &format!("surfaces/{id}/{image_id}.p4i"),
                IMAGE_LIMIT,
            )?;
            let mut spec = im.clone();
            spec.sort_all_objects();
            let spec = serde_json::to_vec(&spec).map_err(|e| e.to_string())?;
            let record = &index[image_id];
            for (key, bytes) in [
                ("source", source.as_slice()),
                ("encoded", encoded.as_slice()),
                ("spec", spec.as_slice()),
            ] {
                if record[key].as_str() != Some(digest(bytes).as_str()) {
                    return Err(format!("stale native image {id}/{image_id}: {key}"));
                }
            }
            validate_image(im, &source, &encoded)?;
            total += encoded.len();
            if total > IMAGE_TOTAL_LIMIT {
                return Err("native UI exceeds 128 KiB image budget".into());
            }
            sprites.push((format!("runtime/images/{image_id}.p4i"), encoded));
        }
    }
    // Reuse the normal OTA compactor, including vars normalization, page label
    // removal and token-usage readers/fetchers filtering. No validator is relaxed.
    let widget_bytes = crate::usb_serial::prepare_native_widget_file(id, &widget_bytes)?;
    Ok(Some(NativeComponent {
        widget_bytes,
        sprites,
    }))
}

fn safe_name(name: &str) -> Result<(), String> {
    if name.is_empty()
        || name.len() > 64
        || !name
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_')
    {
        return Err("unsafe native UI identifier".into());
    }
    Ok(())
}

fn image_asset(image: &Value) -> Result<&str, String> {
    let asset = image["asset"]
        .as_str()
        .ok_or("missing native image asset")?;
    let name = asset
        .strip_prefix("assets/")
        .and_then(|v| v.strip_suffix(".png"))
        .ok_or("unsafe native image asset")?;
    safe_name(name)?;
    Ok(asset)
}

fn digest(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

fn read_bounded(root: &Path, relative: &str, limit: usize) -> Result<Vec<u8>, String> {
    let path = Path::new(relative);
    if relative.is_empty()
        || relative.contains('\\')
        || !path.components().all(|c| matches!(c, Component::Normal(_)))
    {
        return Err("unsafe native UI path".into());
    }
    let root_meta = fs::symlink_metadata(root).map_err(|e| format!("read native UI root: {e}"))?;
    if !root_meta.is_dir() || root_meta.file_type().is_symlink() {
        return Err("native UI root must be a real directory".into());
    }
    let mut full = root.to_path_buf();
    for part in path.components() {
        full.push(part);
        let metadata =
            fs::symlink_metadata(&full).map_err(|e| format!("read {}: {e}", full.display()))?;
        if metadata.file_type().is_symlink() {
            return Err(format!("native UI symlink rejected: {}", full.display()));
        }
    }
    let metadata = fs::metadata(&full).map_err(|e| e.to_string())?;
    if !metadata.is_file() || metadata.len() > limit as u64 {
        return Err(format!("native UI file exceeds bound: {relative}"));
    }
    let mut bytes = Vec::new();
    fs::File::open(full)
        .map_err(|e| e.to_string())?
        .take(limit as u64 + 1)
        .read_to_end(&mut bytes)
        .map_err(|e| e.to_string())?;
    if bytes.len() > limit {
        return Err(format!("native UI file exceeds bound: {relative}"));
    }
    Ok(bytes)
}

fn read_verified(
    root: &Path,
    inventory: &Value,
    relative: &str,
    limit: usize,
) -> Result<Vec<u8>, String> {
    let expected = inventory["files"][relative]
        .as_str()
        .ok_or_else(|| format!("native UI file is not inventoried: {relative}"))?;
    let bytes = read_bounded(root, relative, limit)?;
    if digest(&bytes) != expected {
        return Err(format!("native UI hash mismatch: {relative}"));
    }
    Ok(bytes)
}

fn ensure_only_image_dimensions_changed(original: &Value, native: &Value) -> Result<(), String> {
    let font_images: std::collections::HashSet<&str> = original["surface"]["fonts"]
        .as_array()
        .into_iter()
        .flatten()
        .filter_map(|font| font["image"].as_str())
        .collect();
    let mut original = original.clone();
    let mut native = native.clone();
    for widget in [&mut original, &mut native] {
        if let Some(images) = widget["surface"]["images"].as_array_mut() {
            for image in images {
                // Font sheets retain their glyph grid and pixel metrics.
                if image["id"]
                    .as_str()
                    .is_some_and(|id| font_images.contains(id))
                {
                    continue;
                }
                let object = image
                    .as_object_mut()
                    .ok_or("invalid native image declaration")?;
                object.remove("frame_width");
                object.remove("frame_height");
            }
        }
    }
    if original != native {
        return Err("native UI changed canonical runtime behavior".into());
    }
    Ok(())
}

fn validate_image(spec: &Value, png: &[u8], encoded: &[u8]) -> Result<(), String> {
    let width = spec["frame_width"].as_u64().ok_or("missing image width")?;
    let height = spec["frame_height"]
        .as_u64()
        .ok_or("missing image height")?;
    if width == 0
        || width > 512
        || height == 0
        || height > 240
        || spec["frames"].as_u64() != Some(1)
    {
        return Err("native image dimensions or frames exceed bounds".into());
    }
    if png.len() < 24
        || &png[..8] != b"\x89PNG\r\n\x1a\n"
        || &png[12..16] != b"IHDR"
        || u64::from(u32::from_be_bytes(png[16..20].try_into().unwrap())) != width
        || u64::from(u32::from_be_bytes(png[20..24].try_into().unwrap())) != height
    {
        return Err("native PNG does not match image declaration".into());
    }
    if encoded.len() < 12
        || encoded.len() > IMAGE_LIMIT
        || u32::from_le_bytes(encoded[8..12].try_into().unwrap()) as usize != encoded.len()
    {
        return Err("invalid native encoded image size".into());
    }
    let (actual_width, actual_height) = match &encoded[..4] {
        b"P4I1" if encoded[6..8] == [1, 0] => (u64::from(encoded[4]), u64::from(encoded[5])),
        b"P4I2" | b"P4J1" => (
            u64::from(u16::from_le_bytes(encoded[4..6].try_into().unwrap())),
            u64::from(u16::from_le_bytes(encoded[6..8].try_into().unwrap())),
        ),
        _ => return Err("invalid native encoded image magic".into()),
    };
    if (actual_width, actual_height) != (width, height) {
        return Err("native encoded image dimensions mismatch".into());
    }
    if spec["encoding"] == "jpeg" {
        if &encoded[..4] != b"P4J1"
            || (width, height) != (320, 240)
            || encoded.get(12..14) != Some(&[0xff, 0xd8])
            || !encoded.ends_with(&[0xff, 0xd9])
        {
            return Err("invalid native JPEG background".into());
        }
    } else {
        if !matches!(&encoded[..4], b"P4I1" | b"P4I2") || encoded.len() < 1036 {
            return Err("invalid native palette image".into());
        }
        let mut pixels = 0u64;
        let mut at = 1036;
        while at < encoded.len() {
            let tag = encoded[at];
            at += 1;
            let run = usize::from(tag & 127) + 1;
            at += if tag & 128 != 0 { 1 } else { run };
            pixels += run as u64;
            if at > encoded.len() || pixels > width * height {
                return Err("invalid native image RLE".into());
            }
        }
        if pixels != width * height {
            return Err("incomplete native image RLE".into());
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use std::{fs, path::PathBuf};

    fn repo() -> PathBuf {
        Path::new(env!("CARGO_MANIFEST_DIR"))
            .join(file!())
            .parent()
            .unwrap()
            .join("../../..")
    }
    fn resources() -> PathBuf {
        repo().join("firmware/assets/s3-landscape-ui")
    }
    fn original(id: &str) -> PathBuf {
        repo().join("pc/builtin-clawpkgs").join(id)
    }
    fn copy_tree(from: &Path, to: &Path) {
        fs::create_dir_all(to).unwrap();
        for entry in fs::read_dir(from).unwrap() {
            let entry = entry.unwrap();
            if entry.file_type().unwrap().is_dir() {
                copy_tree(&entry.path(), &to.join(entry.file_name()));
            } else {
                fs::copy(entry.path(), to.join(entry.file_name())).unwrap();
            }
        }
    }

    #[test]
    fn s3_native_ui_uses_runtime_without_display_capability_branching() {
        for status in [
            json!({"runtime":"esp-s3","capabilities":{"display":{"physicalWidth":320,"physicalHeight":240}}}),
            json!({"runtime":"esp-s3","capabilities":{"display":{"physicalWidth":240,"physicalHeight":240}}}),
            json!({"runtime":"esp-s3","capabilities":{"appearance":{"width":240,"height":240}}}),
            json!({"runtime":"esp-s3","capabilities":{}}),
            json!({"runtime":"esp-s3"}),
        ] {
            assert!(uses_native_ui(status["runtime"].as_str().unwrap()));
        }
        for runtime in ["esp-p4", "linux", "", "unknown"] {
            assert!(!uses_native_ui(runtime));
        }
    }

    #[test]
    fn s3_all_canonical_packages_use_bounded_native_artwork() {
        let inventory: Value =
            serde_json::from_slice(&fs::read(resources().join("inventory.json")).unwrap()).unwrap();
        let ids = inventory["components"].as_array().unwrap();
        assert_eq!(ids.len(), 28);
        let mut count = 0;
        let mut declared_count = 0;
        for id in ids {
            let id = id.as_str().unwrap();
            let prepared = prepare_native_component(&resources(), id, &original(id))
                .unwrap()
                .unwrap_or_else(|| panic!("missing native {id}"));
            let widget: Value = serde_json::from_slice(&prepared.widget_bytes).unwrap();
            let canonical: Value = serde_json::from_slice(
                &fs::read(original(id).join("runtime/widget.json")).unwrap(),
            )
            .unwrap();
            declared_count += canonical["surface"]["images"].as_array().map_or(0, Vec::len);
            assert_eq!(
                widget["surface"]["elements"], canonical["surface"]["elements"],
                "{id}"
            );
            assert_eq!(
                widget["surface"]["fonts"], canonical["surface"]["fonts"],
                "{id}"
            );
            assert!(widget["vars"].is_object());
            if id == "token-usage" {
                assert!(widget.get("readers").is_none());
                assert!(widget.get("fetchers").is_none());
            }
            assert!(
                prepared.widget_bytes.len()
                    <= if widget["surface"]["graphics"] == "p4-app-graphics-v1" {
                        8191
                    } else {
                        4095
                    }
            );
            assert!(prepared.sprites.len() <= 4);
            assert!(prepared.sprites.iter().map(|(_, b)| b.len()).sum::<usize>() <= 128 * 1024);
            for (name, bytes) in prepared.sprites {
                let image_id = name
                    .strip_prefix("runtime/images/")
                    .unwrap()
                    .strip_suffix(".p4i")
                    .unwrap();
                let spec = widget["surface"]["images"]
                    .as_array()
                    .unwrap()
                    .iter()
                    .find(|im| im["id"] == image_id)
                    .unwrap();
                assert!(bytes.len() <= 100000);
                assert_eq!(
                    u32::from_le_bytes(bytes[8..12].try_into().unwrap()) as usize,
                    bytes.len()
                );
                let (w, h) = if &bytes[..4] == b"P4I1" {
                    (u16::from(bytes[4]), u16::from(bytes[5]))
                } else {
                    assert!(matches!(&bytes[..4], b"P4I2" | b"P4J1"));
                    (
                        u16::from_le_bytes(bytes[4..6].try_into().unwrap()),
                        u16::from_le_bytes(bytes[6..8].try_into().unwrap()),
                    )
                };
                assert_eq!(u64::from(w), spec["frame_width"].as_u64().unwrap());
                assert_eq!(u64::from(h), spec["frame_height"].as_u64().unwrap());
                count += 1;
            }
        }
        assert_eq!(count, declared_count);
    }

    #[test]
    fn s3_custom_or_modified_originals_keep_normal_install() {
        assert!(prepare_native_component(
            &resources(),
            "custom-component",
            &original("city-radio")
        )
        .unwrap()
        .is_none());
        for file in [
            "runtime/widget.json",
            "buttons.json",
            "component.json",
            "assets/background.png",
        ] {
            let temp = tempfile::tempdir().unwrap();
            copy_tree(&original("city-radio"), temp.path());
            let mut bytes = fs::read(temp.path().join(file)).unwrap();
            bytes.push(b' ');
            fs::write(temp.path().join(file), bytes).unwrap();
            assert!(
                prepare_native_component(&resources(), "city-radio", temp.path())
                    .unwrap()
                    .is_none(),
                "{file}"
            );
        }
    }

    #[test]
    fn s3_corrupt_native_resources_fail_instead_of_silent_fallback() {
        for file in [
            "inventory.json",
            "packages/city-radio/runtime/widget.json",
            "packages/city-radio/assets/background.png",
            "surfaces/city-radio/index.json",
            "surfaces/city-radio/background.p4i",
        ] {
            let temp = tempfile::tempdir().unwrap();
            copy_tree(&resources(), temp.path());
            let mut bytes = fs::read(temp.path().join(file)).unwrap();
            bytes.push(0);
            fs::write(temp.path().join(file), bytes).unwrap();
            assert!(
                prepare_native_component(temp.path(), "city-radio", &original("city-radio"))
                    .is_err(),
                "{file}"
            );
        }
    }

    #[test]
    fn s3_package_ids_cannot_escape_resource_root() {
        for id in [
            "../city-radio",
            "/city-radio",
            "city-radio/../../x",
            "city-radio\\x",
            ".",
            "",
        ] {
            assert!(
                prepare_native_component(&resources(), id, &original("city-radio")).is_err(),
                "{id}"
            );
        }
    }

    #[test]
    fn s3_runtime_substitution_preserves_behavior_and_font_dimensions() {
        let original = json!({"surface":{
            "images":[{"id":"background","asset":"assets/background.png","frame_width":640,"frame_height":480,"frames":1,"fps":1,"encoding":"jpeg"},
                      {"id":"glyphs","asset":"assets/glyphs.png","frame_width":224,"frame_height":160,"frames":1,"fps":1}],
            "fonts":[{"image":"glyphs","glyph_width":16,"glyph_height":16}],
            "elements":[{"type":"text","text":"Keep me","x":10}]},
            "transitions":[{"on":"play"}]});
        let mut native = original.clone();
        native["surface"]["images"][0]["frame_width"] = json!(320);
        native["surface"]["images"][0]["frame_height"] = json!(240);
        assert!(ensure_only_image_dimensions_changed(&original, &native).is_ok());
        for pointer in [
            "/surface/elements/0/text",
            "/transitions/0/on",
            "/surface/images/0/encoding",
            "/surface/fonts/0/glyph_width",
            "/surface/images/1/frame_width",
        ] {
            let mut modified = native.clone();
            *modified.pointer_mut(pointer).unwrap() = json!(99);
            assert!(
                ensure_only_image_dimensions_changed(&original, &modified).is_err(),
                "{pointer}"
            );
        }
    }

    #[test]
    fn s3_image_validation_rejects_header_dimensions_rle_and_budget_errors() {
        let widget: Value = serde_json::from_slice(
            &fs::read(resources().join("packages/city-radio/runtime/widget.json")).unwrap(),
        )
        .unwrap();
        let spec = &widget["surface"]["images"][1];
        let png = fs::read(resources().join("packages/city-radio/assets/vinyl.png")).unwrap();
        let encoded = fs::read(resources().join("surfaces/city-radio/vinyl.p4i")).unwrap();
        assert!(validate_image(spec, &png, &encoded).is_ok());
        let mut bad = encoded.clone();
        bad[4] = 1;
        assert!(validate_image(spec, &png, &bad).is_err());
        let mut bad = encoded.clone();
        bad.pop();
        let size = bad.len() as u32;
        bad[8..12].copy_from_slice(&size.to_le_bytes());
        assert!(validate_image(spec, &png, &bad).is_err());
        let mut bad = encoded.clone();
        bad.resize(100001, 0);
        let size = bad.len() as u32;
        bad[8..12].copy_from_slice(&size.to_le_bytes());
        assert!(validate_image(spec, &png, &bad).is_err());
        let mut bad_png = png.clone();
        bad_png[19] = 1;
        assert!(validate_image(spec, &bad_png, &encoded).is_err());
    }

    #[cfg(unix)]
    #[test]
    fn s3_symlinked_resource_and_original_files_are_not_followed() {
        use std::os::unix::fs::symlink;
        let temp = tempfile::tempdir().unwrap();
        copy_tree(&resources(), temp.path());
        let path = temp.path().join("surfaces/city-radio/background.p4i");
        fs::remove_file(&path).unwrap();
        symlink(
            resources().join("surfaces/city-radio/background.p4i"),
            &path,
        )
        .unwrap();
        assert!(
            prepare_native_component(temp.path(), "city-radio", &original("city-radio")).is_err()
        );
        let temp = tempfile::tempdir().unwrap();
        copy_tree(&original("city-radio"), temp.path());
        let path = temp.path().join("assets/background.png");
        fs::remove_file(&path).unwrap();
        symlink(original("city-radio").join("assets/background.png"), &path).unwrap();
        assert!(
            prepare_native_component(&resources(), "city-radio", temp.path())
                .unwrap()
                .is_none()
        );
    }
}

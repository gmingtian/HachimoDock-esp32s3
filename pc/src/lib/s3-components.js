import policy from "../../../firmware/s3/component-policy.json" with { type: "json" };

export function componentSupportedOnTarget(id, runtime = "esp-s3") {
  return runtime !== "esp-s3" || !policy.unsupportedBuiltins.includes(id);
}
export function filterTargetComponents(items, runtime = "esp-s3") {
  return items.filter((item) => componentSupportedOnTarget(item.id, runtime));
}

import type { DataAsset, GroundTruthSet } from "../api/client";

type GroundTruthEvaluationSelectorProps = {
  dataAssets: DataAsset[];
  groundTruthSets: GroundTruthSet[];
  onChange: (groundTruthSetId: string) => void;
  selectedGroundTruthSetId: string;
};

export function compatibleGroundTruthSets(
  groundTruthSets: GroundTruthSet[],
  dataAssetId: string | null,
): GroundTruthSet[] {
  if (!dataAssetId) {
    return [];
  }
  return groundTruthSets.filter(
    (groundTruthSet) =>
      groundTruthSet.data_asset_id == null || groundTruthSet.data_asset_id === dataAssetId,
  );
}

export function reconcileGroundTruthSelection(
  selectedGroundTruthSetId: string,
  groundTruthSets: GroundTruthSet[],
): string {
  return groundTruthSets.some((groundTruthSet) => groundTruthSet.id === selectedGroundTruthSetId)
    ? selectedGroundTruthSetId
    : "";
}

export function hasValidGroundTruthSelection(
  selectedGroundTruthSetId: string,
  groundTruthSets: GroundTruthSet[],
): boolean {
  return Boolean(
    selectedGroundTruthSetId &&
      groundTruthSets.some((groundTruthSet) => groundTruthSet.id === selectedGroundTruthSetId),
  );
}

export function GroundTruthEvaluationSelector({
  dataAssets,
  groundTruthSets,
  onChange,
  selectedGroundTruthSetId,
}: GroundTruthEvaluationSelectorProps) {
  return (
    <label className="wide-field">
      Ground Truth Set
      <select
        disabled={groundTruthSets.length === 0}
        value={selectedGroundTruthSetId}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">
          {groundTruthSets.length === 0
            ? "No compatible Ground Truth Sets"
            : "Select a Ground Truth Set"}
        </option>
        {groundTruthSets.map((groundTruthSet) => (
          <option key={groundTruthSet.id} value={groundTruthSet.id}>
            {groundTruthOptionLabel(groundTruthSet, dataAssets)}
          </option>
        ))}
      </select>
    </label>
  );
}

function groundTruthOptionLabel(
  groundTruthSet: GroundTruthSet,
  dataAssets: DataAsset[],
): string {
  const dataAsset = groundTruthSet.data_asset_id
    ? dataAssets.find((asset) => asset.id === groundTruthSet.data_asset_id)
    : null;
  const dataLabel = groundTruthSet.data_asset_id
    ? dataAsset?.name || `data ${shortId(groundTruthSet.data_asset_id)}`
    : "unlinked";
  const canonicalSha = shortCanonicalSha(groundTruthSet.metadata_json.canonical_sha256);
  return [groundTruthSet.name, dataLabel, canonicalSha ? `SHA ${canonicalSha}` : null]
    .filter(Boolean)
    .join(" · ");
}

function shortCanonicalSha(value: unknown): string | null {
  if (typeof value !== "string" || !value.trim()) {
    return null;
  }
  return value.replace(/^sha256:/, "").slice(0, 12);
}

function shortId(value: string): string {
  return value.length <= 12 ? value : `${value.slice(0, 12)}…`;
}

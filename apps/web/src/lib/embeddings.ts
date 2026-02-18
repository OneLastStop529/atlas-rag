export type EmbeddingsProviderId =
  | "sentence-transformers"
  | "hash"
  | "hf_local"
  | "tei"
  | "bge-small-zh"
  | "bge-large-zh";

export const EMBEDDINGS_PROVIDER_OPTIONS: Array<{
  value: EmbeddingsProviderId;
  label: string;
}> = [
  { value: "sentence-transformers", label: "Sentence Transformers" },
  { value: "hash", label: "Hash" },
  { value: "hf_local", label: "HF Local" },
  { value: "tei", label: "TEI" },
  { value: "bge-small-zh", label: "BGE Small (ZH)" },
  { value: "bge-large-zh", label: "BGE Large (ZH)" },
];

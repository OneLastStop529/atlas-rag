"use client"

import { useState } from "react";
import { uploadFile } from "@lib/upload";

export default function UploadPage() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL!;
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  async function onUpload() {
    if (!file) return;
    setUploading(true);
    setResult(null);
    try {
      const r = await uploadFile(apiUrl, file);
      setResult(r);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  }
}

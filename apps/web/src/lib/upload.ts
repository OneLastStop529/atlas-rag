export async function uploadFile(apiUrl: string, file: File) {
  const fd = new FormData();
  fd.append('file', file);

  const response = await fetch(`${apiUrl}/upload`, {
    method: 'POST',
    body: fd,
  })

  if (!response.ok) throw new Error(`Upload failed: HTTP ${response.status}`);

  return response.json();
}

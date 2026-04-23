export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface LogoOverlayResponse {
  status: string
  message: string
  data: {
    output_path: string
  }
}

export async function uploadLogoOverlay(formData: FormData): Promise<LogoOverlayResponse> {
  const response = await fetch(`${API_BASE_URL}/v1/overlay/logo`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    throw new Error('Failed to upload overlay')
  }

  return response.json()
}
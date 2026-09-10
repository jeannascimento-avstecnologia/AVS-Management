import { domToPng } from 'modern-screenshot'

export async function captureViewportScreenshot(): Promise<string> {
  const dataUrl = await domToPng(document.documentElement, {
    quality: 0.85,
    scale: window.devicePixelRatio || 1,
  })
  return dataUrl
}

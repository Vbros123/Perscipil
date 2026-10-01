import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { readFileSync } from 'node:fs'

const { brand } = JSON.parse(readFileSync(new URL('../product.json', import.meta.url), 'utf8'))
const imageUrl = `https://${process.env.VERCEL_URL || 'privatelens.vercel.app'}/brand/perspicil-social.svg`
const manifest = JSON.stringify({
  name: brand.name, short_name: brand.short_name, description: brand.description,
  start_url: '/', display: 'standalone', background_color: '#0b1017', theme_color: '#0b1017',
  icons: [192, 512].map(size => ({ src: `/brand/perspicil-${size}.png`, sizes: `${size}x${size}`, type: 'image/png' })),
})
const escapeHtml = value => value.replaceAll('&', '&amp;').replaceAll('"', '&quot;').replaceAll('<', '&lt;')
const branding = {
  name: 'product-branding',
  transformIndexHtml: html => html.replaceAll('%BRAND_TITLE%', escapeHtml(brand.title)).replaceAll('%BRAND_DESCRIPTION%', escapeHtml(brand.description)).replaceAll('%BRAND_NAME%', escapeHtml(brand.name)).replaceAll('%BRAND_IMAGE_URL%', escapeHtml(imageUrl)),
  generateBundle() { this.emitFile({ type: 'asset', fileName: 'manifest.webmanifest', source: manifest }) },
  configureServer(server) {
    server.middlewares.use('/manifest.webmanifest', (_req, res) => { res.setHeader('Content-Type', 'application/manifest+json'); res.end(manifest) })
  },
}

export default defineConfig({
  plugins: [react(), branding],
  server: { port: 5173, strictPort: true },
  build: { outDir: 'dist' }
})

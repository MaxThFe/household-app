import sharp from 'sharp'

const BG = '#F5EDE4'
const FG = '#4A3F35'

function makeSvg(size) {
  const cx = size / 2
  const pad = size * 0.19

  const roofTop    = pad
  const eaveY      = size * 0.48
  const wallLeft   = size * 0.26
  const wallRight  = size * 0.74
  const wallBottom = size * 0.83
  const doorLeft   = cx - size * 0.11
  const doorRight  = cx + size * 0.11
  const doorTop    = size * 0.64
  const sw         = size * 0.055

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}">
  <rect width="${size}" height="${size}" fill="${BG}"/>
  <g fill="none" stroke="${FG}" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round">
    <polyline points="${pad + sw/2},${eaveY} ${cx},${roofTop + sw/2} ${size - pad - sw/2},${eaveY}"/>
    <path d="M${wallLeft},${eaveY} L${wallLeft},${wallBottom} L${doorLeft},${wallBottom} L${doorLeft},${doorTop} L${doorRight},${doorTop} L${doorRight},${wallBottom} L${wallRight},${wallBottom} L${wallRight},${eaveY}"/>
  </g>
</svg>`
}

for (const size of [192, 512]) {
  await sharp(Buffer.from(makeSvg(size))).png().toFile(`public/icon-${size}.png`)
  console.log(`icon-${size}.png written`)
}

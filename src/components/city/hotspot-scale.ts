/** Circle area proportional to the count: radius ∝ √n (pixels). */
export function hotspotRadius(n: number, max: number) {
  return 5 + 26 * Math.sqrt(n / Math.max(1, max));
}

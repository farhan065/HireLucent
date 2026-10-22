// The face guide on the identity photo step (F7): from the faces MediaPipe
// finds in the camera picture, the one tip to show, and whether the border
// is green. Positions are shares of the picture (0 to 1), so they work for
// any camera size. The limits follow the face-match test: turned heads
// matched worst, while dim light and sitting back still matched well.

// The oval on the preview: centre and size as shares of the picture.
export const OVAL = { x: 0.5, y: 0.46, width: 0.33, height: 0.69 }
// How long the border must stay green before the photo is taken by itself.
export const GREEN_SECONDS = 5

const MIN_WIDTH = 0.18
const MAX_WIDTH = 0.5
const MAX_OFFSET_X = 0.12
const MAX_OFFSET_Y = 0.15
const EDGE = 0.02
// Nose away from the middle of the eyes, as a share of the eye distance.
const MAX_TURN = 0.25
// Average light of the face, 0 dark to 255 bright. Only a really dark face.
const MIN_LIGHT = 45

export const TIPS = {
  starting: 'Starting the face guide…',
  none: 'Put your face inside the oval',
  several: 'Only one person, please',
  closer: 'Move closer',
  back: 'Move back',
  centre: 'Centre your face in the oval',
  straight: 'Look straight at the camera',
  dark: 'Too dark: face the light',
  good: 'Looks good. Hold still',
}

// faces: [{ x, y, width, height, eyes: [[x, y], [x, y]] | null, nose: [x, y] | null }]
// in shares of the picture. light: the face's average light, or null.
export function guideTip(faces, light) {
  if (faces.length === 0) return 'none'
  if (faces.length > 1) return 'several'
  const face = faces[0]
  const touchesEdge =
    face.x < EDGE ||
    face.y < EDGE ||
    face.x + face.width > 1 - EDGE ||
    face.y + face.height > 1 - EDGE
  if (face.width > MAX_WIDTH || touchesEdge) return 'back'
  if (face.width < MIN_WIDTH) return 'closer'
  const centreX = face.x + face.width / 2
  const centreY = face.y + face.height / 2
  if (Math.abs(centreX - OVAL.x) > MAX_OFFSET_X || Math.abs(centreY - OVAL.y) > MAX_OFFSET_Y) {
    return 'centre'
  }
  if (face.eyes && face.nose) {
    const [[rightX, rightY], [leftX, leftY]] = face.eyes
    const gap = Math.hypot(leftX - rightX, leftY - rightY) || 1
    if (Math.abs(face.nose[0] - (rightX + leftX) / 2) / gap > MAX_TURN) return 'straight'
  }
  if (light !== null && light < MIN_LIGHT) return 'dark'
  return 'good'
}

// The space kept on every side of the face when the photo is cut out, as a
// share of the face's own width and height. The server's face models need
// this room: in testing, a tight cut (half a face) lowered the match score
// from 0.92 to as little as 0.62, while one full face of space scored as
// well as the whole picture (0.95).
const CROP_MARGIN = 1

// The part of the camera picture sent for the identity check: the face the
// guide found, with space around it, in pixels and kept inside the picture.
// It follows the face, so it fits a small or a large face, and people
// further back in the room are left out.
export function faceCrop(face, pictureWidth, pictureHeight) {
  const left = Math.max(0, (face.x - face.width * CROP_MARGIN) * pictureWidth)
  const top = Math.max(0, (face.y - face.height * CROP_MARGIN) * pictureHeight)
  const right = Math.min(pictureWidth, (face.x + face.width * (1 + CROP_MARGIN)) * pictureWidth)
  const bottom = Math.min(pictureHeight, (face.y + face.height * (1 + CROP_MARGIN)) * pictureHeight)
  return {
    x: Math.round(left),
    y: Math.round(top),
    width: Math.round(right - left),
    height: Math.round(bottom - top),
  }
}

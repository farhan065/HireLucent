// Puts the files of the face guide (candidate identification, F7) where the
// app serves them, so the candidate's browser loads them from HireLucent
// itself and no camera picture ever goes to another site:
//   public/mediapipe/wasm/  MediaPipe's runtime, copied from node_modules
//   public/mediapipe/blaze_face_short_range.tflite  the face model (Apache 2.0),
//                           downloaded once
// Runs before "npm run dev" and "npm run build". If the model cannot be
// downloaded, the build still works: the photo step then has no live tips
// and the photo is checked on the server only.
import { copyFile, mkdir, stat, writeFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const source = join(root, 'node_modules/@mediapipe/tasks-vision/wasm')
const target = join(root, 'public/mediapipe')
const WASM_FILES = [
  'vision_wasm_internal.js',
  'vision_wasm_internal.wasm',
  'vision_wasm_nosimd_internal.js',
  'vision_wasm_nosimd_internal.wasm',
]
const MODEL = 'blaze_face_short_range.tflite'
const MODEL_URL = `https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/${MODEL}`

async function exists(path) {
  try {
    return (await stat(path)).size > 0
  } catch {
    return false
  }
}

await mkdir(join(target, 'wasm'), { recursive: true })
for (const name of WASM_FILES) {
  await copyFile(join(source, name), join(target, 'wasm', name))
}

const modelPath = join(target, MODEL)
if (!(await exists(modelPath))) {
  try {
    const response = await fetch(MODEL_URL)
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    await writeFile(modelPath, Buffer.from(await response.arrayBuffer()))
    console.log(`Face guide model downloaded to public/mediapipe/${MODEL}`)
  } catch (error) {
    console.warn(`The face guide model could not be downloaded (${error.message}).`)
    console.warn('The photo step will work without live tips.')
  }
}

import assert from 'node:assert/strict';
import test from 'node:test';
import { validateUpload, uploadError, uploadPhase, validUploadLimits } from '../src/api/uploadValidation.js';

const limits = {
  image: { max_bytes: 10 * 1024 * 1024, extensions: ['.jpg', '.jpeg', '.png', '.webp'] },
  video: { max_bytes: 100 * 1024 * 1024, extensions: ['.mp4', '.avi', '.mov'] },
};
test('upload validation uses backend-provided limits, rejects empty/oversized/unsupported files', () => {
  assert.equal(validUploadLimits(limits), true);
  assert.equal(validUploadLimits({}), false);
  assert.equal(validUploadLimits({ image: { max_bytes: -1, extensions: [] } }), false);
  assert.equal(validateUpload({ name: 'PPE.JPG', size: 123 }, 'image', limits), null);
  assert.equal(validateUpload({ name: 'workers.mp4', size: limits.video.max_bytes }, 'video', limits), null);
  assert.match(validateUpload({ name: 'x.gif', size: 123 }, 'image', limits), /Allowed image types/);
  assert.match(validateUpload({ name: 'x.png', size: 0 }, 'image', limits), /empty/);
  assert.match(validateUpload({ name: 'x.png', size: limits.image.max_bytes + 1 }, 'image', limits), /10 MiB/);
  assert.match(validateUpload({ name: 'x.mp4', size: limits.video.max_bytes + 1 }, 'video', limits), /100 MiB/);
  assert.match(validateUpload({ name: 'x.png', size: 123 }, 'image', null), /not available/);
});
test('clear errors preserve HTTP rejection details and validation messages', () => {
  assert.equal(uploadError({ response: { data: { detail: 'The image is corrupt' } } }), 'The image is corrupt');
  assert.equal(uploadError({ response: { data: { detail: [{ msg: 'Invalid cooldown' }] } } }), 'Invalid cooldown');
  assert.equal(uploadError({ message: 'Network Error' }), 'Network Error');
});
test('network progress and backend processing are distinct and never invent processing percent', () => {
  assert.equal(uploadPhase('pending'), 'Queued');
  assert.equal(uploadPhase('uploading', 42), 'Uploading 42%');
  assert.equal(uploadPhase('uploading', null), 'Uploading…');
  assert.equal(uploadPhase('processing', 100), 'Processing on backend…');
  assert.equal(uploadPhase('done'), 'Done');
  assert.equal(uploadPhase('error'), 'Error');
});

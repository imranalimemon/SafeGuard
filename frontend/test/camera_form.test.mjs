import test from 'node:test';
import assert from 'node:assert/strict';
import { cameraUpdatePayload, cameraErrorMessage } from '../src/api/cameraForm.js';

test('editing metadata never submits an empty password that erases stored credentials', () => {
  const form = { name: 'Camera A', password: '', username: 'operator', location: 'Updated', enabled: false };
  assert.deepEqual(cameraUpdatePayload(form), { name: 'Camera A', username: 'operator', location: 'Updated', enabled: false });
  assert.equal(form.password, '');
  assert.equal(cameraUpdatePayload({ ...form, password: 'replacement' }).password, 'replacement');
});

test('FastAPI validation arrays become renderable messages instead of crashing React', () => {
  const error = { response: { data: { detail: [{ msg: 'At most 120 characters' }, { msg: 'Invalid source' }] } } };
  assert.equal(cameraErrorMessage(error), 'At most 120 characters; Invalid source');
});

test('delete/test failures preserve real server or network errors for the UI', () => {
  assert.equal(cameraErrorMessage({ response: { data: { detail: 'Synthetic delete failure' } } }), 'Synthetic delete failure');
  assert.equal(cameraErrorMessage(new Error('Network Error')), 'Network Error');
  assert.equal(cameraErrorMessage({}, 'Failed to delete camera.'), 'Failed to delete camera.');
});

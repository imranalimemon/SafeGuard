import React from 'react';

export default function HelpPage() {
  return <article className="p-6 overflow-auto space-y-4" style={{ maxWidth: 1000 }}>
    <h1 className="text-2xl font-bold">Safety Protocols and Help</h1>
    <section><h2 className="text-xl font-bold">Before monitoring</h2><p>Check backend, model and database health. Add a camera, test it, then select it on the Dashboard and press Start. Review the site's required PPE and alert recipients in Settings.</p></section>
    <section><h2 className="text-xl font-bold">Review each incident</h2><p>Open evidence before deciding whether a violation is valid. Acknowledge records review; Escalate records that follow-up is needed. Archive hides evidence from the default list without deleting it. Exports respect the active filters.</p></section>
    <section><h2 className="text-xl font-bold">Mask assessment limits</h2><p>A missing mask is assessed only when the worker is large enough and the face-visibility heuristic accepts the head region. “Mask not assessable” is unknown, not proof of compliance. Occlusion, lighting and missed detections can cause incorrect results. A human safety review remains necessary.</p></section>
    <section><h2 className="text-xl font-bold">Alert delivery</h2><p>Preview mode builds messages without contacting SMTP or Twilio. Use the email preview to inspect source, time, missing PPE and evidence. Live delivery requires deliberate deployment configuration; do not enable it until recipients and credentials are verified.</p></section>
    <section><h2 className="text-xl font-bold">Connection problems</h2><p>The stream retries a failed camera with bounded backoff and clears stale frames. After retries are exhausted, check the camera source and press Start again. System Logs contains operational errors. A physical camera driver can still hang; restart the backend if it fails to release the device.</p></section>
    <p>This system records and assists safety review. It does not physically stop machinery or replace site safety procedures.</p>
  </article>;
}

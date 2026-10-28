"""ONNX provider selection; graph/postprocessing and thresholds are unchanged."""
import logging


def create_session(runtime, path):
    available = runtime.get_available_providers()
    accelerated = [name for name in ('CUDAExecutionProvider', 'DmlExecutionProvider') if name in available]
    providers = accelerated + ['CPUExecutionProvider']
    options = runtime.SessionOptions()
    if 'DmlExecutionProvider' in providers:
        options.enable_mem_pattern = False
        options.execution_mode = runtime.ExecutionMode.ORT_SEQUENTIAL
    try:
        return runtime.InferenceSession(path, sess_options=options, providers=providers)
    except Exception:
        if not accelerated:
            raise
        logging.getLogger('safeguard.model').warning('Accelerator initialization failed; retrying CPU provider.')
        return runtime.InferenceSession(path, providers=['CPUExecutionProvider'])

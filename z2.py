import torch
print("torch:", torch.__version__)
print("cuda available?:", torch.cuda.is_available())
print("compiled with cuda?:", torch.version.cuda is not None)
if torch.cuda.is_available():
    print("gpu:", torch.cuda.get_device_name(0))

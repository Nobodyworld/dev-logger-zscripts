import matplotlib.pyplot as plt
import torch

device = "cuda" if torch.cuda.is_available() else "cpu"  # will be "cpu" on your setup
x = torch.randn(10_000, device=device)      # or cpu
plt.hist(x.detach().cpu().numpy(), bins=50);  # visualize
plt.show()

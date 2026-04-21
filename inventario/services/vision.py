import torch
import clip
from PIL import Image

torch.set_num_threads(2)
device = "cuda" if torch.cuda.is_available() else "cpu"
model, preprocess = clip.load("ViT-B/32", device=device)

def generar_embedding(file):
    img = preprocess(Image.open(file)).unsqueeze(0).to(device)
    with torch.no_grad():
        emb = model.encode_image(img)
    emb = emb / emb.norm(dim=-1, keepdim=True)
    return emb.cpu().numpy().tolist()[0]
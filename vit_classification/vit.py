import sys
import torch.nn as nn
import torch

sys.path.append("../transformer_captioning") 
from transformer import (
    AttentionLayer,
    MultiHeadAttentionLayer,
    PositionalEncoding,
    SelfAttentionBlock,
    CrossAttentionBlock,
    FeedForwardBlock
)

class EncoderLayer(nn.Module):
    def __init__(self, d_model, num_heads, d_ff=2048, dropout=0.1):
        super().__init__()
        self.self_attention = SelfAttentionBlock(d_model, num_heads, dropout=dropout)
        self.feed_forward = FeedForwardBlock(d_model, d_ff, dropout=dropout)

    def forward(self, seq, mask):
        x = self.self_attention(seq, mask)
        x = self.feed_forward(x)

        return x

class ViT(nn.Module):
    """
        - A ViT takes an image as input, divides it into patches, and then feeds the patches through a transformer to output a sequence of patch embeddings. 
        - To perform classification with a ViT we patchify the image, embed each patch using an embedding layer and add a learnable [CLS] token to the beginning of the sequence.
        - The output embedding corresponding to the [CLS] token is then fed through a linear layer to obtain the logits for each class.
    """

    def __init__(self, patch_dim, d_model, d_ff, num_heads, num_layers, num_patches, num_classes, device = 'cuda'):
        """
            Construct a new ViT instance.
            Inputs
            - patch_dim: the dimension of each patch
            - d_model: embedding dimension for per patch; the dimension of the input (embeddings) to the transformer blocks
            - d_ff: the dimension of the intermediate layer in the feed forward block 
            - num_heads: the number of heads in the multi head attention layer
            - num_layers: the number of transformer blocks
            - num_patches: the number of patches in the image
        """

        super().__init__()

        self.patch_dim = patch_dim
        self.d_model = d_model
        self.d_ff = d_ff
        self.num_heads = num_heads
        self.num_layers = num_layers
        self.num_patches = num_patches
        self.num_classes = num_classes
        self.device = device
        
        # TODO - Initialize following layers
        """Patch Embedding Layer"""
        self.patch_embedding = nn.Linear(patch_dim*patch_dim*3, d_model) # Linear Layer that takes as input a patch (patch_dim*patch_dim*3) and outputs a d_model dimensional vector
        """Positional Encoding Layer"""
        self.positional_encoding = PositionalEncoding(embed_dim=d_model, dropout=0.1, max_len=5000) # positional encoding
        """Final Linear Classification Layer"""
        self.fc = nn.Linear(d_model, num_classes)# takes as input the embedding corresponding to the [CLS] token and outputs the logits for each class
        """CLS Token Embedding
        - Shape: (batch size = 1, number of [CLS] token per input sequence = 1, dim of embedding = d_model)
        - We use nn.Parameter() to make CLS token embedding tensor as a learnable parameter so that ts gradients will be computed and updated during backpropagation.
        - The [CLS] token is designed to capture global information in a Vision Transformer (ViT) by aggregating local information from all the patches of the image.
            The [CLS] token is usually placed at the beginning of the input sequence. This position allows it to be processed by the self-attention mechanism 
            in the transformer, enabling it to attend to all other positions (patches) in the sequence."""
        self.cls_token = nn.Parameter(torch.randn(1, 1, d_model)) # (N=1,1,d_model); learnable [CLS] token embedding
        
        self.layers = nn.ModuleList([EncoderLayer(d_model, num_heads, d_ff) for _ in range(num_layers)])

        self.apply(self._init_weights)
        self.device = device 
        self.to(device)

    def patchify(self, images):
        """
            Given a batch of images, divide each image into patches and flatten each patch into a vector.
            Inputs:
                - images: a FloatTensor of shape (N, 3, H, W) giving a minibatch of images
            Returns:
                - patches: a FloatTensor of shape (N, num_patches, patch_dim x patch_dim x 3) giving a minibatch of patches    
        """

        # TODO - Break images into a grid of patches
        """Patchify K (patch_dim x patch_dim) patches from each image in the batch."""
        N,C,H,W = images.shape # N = batch size, C = num channels, H = height, W = width
        patches = images.unfold(dimension=2, size=self.patch_dim, step=self.patch_dim).unfold(dimension=3, size=self.patch_dim, step=self.patch_dim) # (N, C, num_vertical_slices, num_horizontal_slices, patch_dim, patch_dim)
        patches.permute(0, 2, 3, 1, 4, 5) # (N, num_vertical_slices, num_horizontal_slices, C, patch_dim, patch_dim)
        patches = patches.reshape(N, -1, self.patch_dim * self.patch_dim * C) # (N, num_vertical_slices * num_horizontal_slices = num_patches, patch_dim * patch_dim * C)
        return patches

    def forward(self, images):
        """
            Given a batch of images, compute the logits for each class. 
            Inputs:
                - images: a FloatTensor of shape (N, 3, H, W) giving a minibatch of images
            Returns:
                - logits: a FloatTensor of shape (N, C) giving the logits for each class
        """
        
        """Patchify input images (e.g. 16 8x8 patches per 32x32 image)"""
        patches = self.patchify(images) # (N, num_patches, patch_dim * patch_dim * C)
        """Generate an embedding vector per patch (e.g. 1x256 embedding vector per patch)"""
        patches_embedded = self.patch_embedding(patches) # (N, num_patches, d_model)
        
        # TODO - Append a CLS token to the beginning of the sequence of patch embeddings
        """Append a CLS token of shape (N=1,1,d_model) to the beginning of the sequence of patch embeddings of shape (N, num_patches, d_model)"""
        cls_token_repeat = self.cls_token.repeat(patches_embedded.shape[0], 1, 1) # (1, 1, d_model) -> (N, 1, d_model)
        output = torch.cat((cls_token_repeat, patches_embedded), dim=1) # (N, num_patches + 1, d_model)

        output = self.positional_encoding(patches_embedded)
        mask = torch.ones((self.num_patches, self.num_patches), device=self.device)

        for layer in self.layers:
            output = layer(output, mask)

        # TODO (take the embedding corresponding to the [CLS] token and feed it through a linear layer to obtain the logits for each class)
        """Extract embedding vector corresponding to the [CLS] token; 
        Remember that the [CLS] embedding is the first embedding in the sequence of patch embeddings"""
        cls_embedding = output[:, 0, :] # (N, d_model)
        output = self.fc(cls_embedding) # (N, num_classes)

        return output

    def _init_weights(self, module):
        """
        Initialize the weights of the network.
        """
        if isinstance(module, (nn.Linear, nn.Embedding)):
            module.weight.data.normal_(mean=0.0, std=0.02)
            if isinstance(module, nn.Linear) and module.bias is not None:
                module.bias.data.zero_()
        elif isinstance(module, nn.LayerNorm):
            module.bias.data.zero_()
            module.weight.data.fill_(1.0)





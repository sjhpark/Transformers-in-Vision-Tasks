# Credit to the CS-231n course at Stanford, from which this assignment is adapted
import numpy as np
import copy
import math
import torch
import torch.nn as nn
from torch.nn import functional as F

class AttentionLayer(nn.Module):

    def __init__(self, embed_dim, dropout=0.1):
       
        super().__init__()
        self.embed_dim = embed_dim # embedding dimension D
        # TODO: Initialize the following layers and parameters to perform attention
        # This class assumes that the input dimension for query, key and value is embed_dim
        """W_q, W_k, W_v: Linear transformation (projection) layers for Query, Key, Value"""
        self.query_proj = nn.Linear(embed_dim, embed_dim) # linear transformation (projection) layer for Query
        self.key_proj = copy.deepcopy(self.query_proj) # linear transformation (projection) layer for Key
        self.value_proj = copy.deepcopy(self.query_proj) # linear transformation (projection) layer for Value

        self.dropout = nn.Dropout(p=dropout)
            
    def forward(self, query, key, value, attn_mask=None):
        """
        N: Batch Size
        S: Sequence Length of query
        T: Sequence Length of key/value
        D: Embedding Dimension
        """
        N, S, D = query.shape
        N, T, D = value.shape
        assert key.shape == value.shape
       
        # TODO : Compute attention 
    
        #project query, key and value
        """Q, K, V""" 
        query = self.query_proj(query) # (N,S,D); linearly projected query
        key = self.query_proj(key) # (N,T,D); # linearly projected key
        value = self.query_proj(value) # (N,T,D); # linearly projected value

        #compute dot-product attention. Don't forget the scaling value!
        #Expected shape of dot_product is (N, S, T)
        """Scale factor = sqrt(embedding dimension)"""
        scale_factor = math.sqrt(D)
        """Attention scores (dot product) = Q @ K^T"""
        dot_product = (query @ key.transpose(-2,-1))
        """Scaled attention scores (scaled dot product) = (Q @ K^T) / sqrt(embedding dimension)"""
        scaled_attn_scores = dot_product / scale_factor

        if attn_mask is not None:
            # convert att_mask which is multiplicative, to an additive mask
            # If mask[i,j] = 0, we want softmax(QKT[i,j] + additive_mask[i,j]) to be 0
            # Softmax is 0 when e^x = 0, so x could be any big negative number
            """Additive attention mask"""
            big_negative_num = -1e9
            # attn_mask is a boolean lower triangular matrix
            additive_mask = (1 - attn_mask.float()) * big_negative_num
            """Masked scaled attention scores = scaled attention scores + additive mask"""
            scaled_attn_scores += additive_mask
        
        # apply softmax, dropout, and use value
        """Attnetion probabilities = softmax(scaled attention scores)"""
        attn_probs = self.dropout(F.softmax(scaled_attn_scores, dim=-1))
        """Output = attention probabilities @ V"""
        y = attn_probs @ value
        return y

class MultiHeadAttentionLayer(AttentionLayer):

    def __init__(self, embed_dim, num_heads, dropout=0.1):
       
        super().__init__(embed_dim, dropout)
        self.num_heads = num_heads
        assert embed_dim % num_heads == 0, "Dimension of the model should be divisible by the number of heads."

        # TODO: Initialize the following layers and parameters to perform attention
        self.head_proj = nn.Linear(embed_dim, embed_dim) # linear transformation (projection) layer

    def forward(self, query, key, value, attn_mask=None):
        """
        H: Number of heads
        N: Batch Size
        S: Sequence Length of query
        T: Sequence Length of key/value
        D: Embedding Dimension
        """
        H = self.num_heads
        N, S, D = query.shape
        N, T, D = value.shape
        assert key.shape == value.shape

        # TODO : Compute multi-head attention
 
        #project query, key and value
        #after projection, split the embedding across num_heads
        #eg - expected shape for value is (N, H, T, D/H)
        """Q_i, K_i, V_i where i is the head number"""
        query = self.head_proj(query).view(N, S, H, D//H) # (N,S,D) -> (N,S,H,D/H)
        key = self.head_proj(key).view(N, T, H, D//H) # (N,T,D) -> (N,T,H,D/H)
        value = self.head_proj(value).view(N, T, H, D//H) # (N,T,D) -> (N,T,H,D/H)

        """Transpose Q_i, K_i, V_i to reorder the dimensions"""
        query = query.transpose(1,2) # (N,S,H,D/H) -> (N,H,S,D/H)
        key = key.transpose(1,2) # (N,T,H,D/H) -> (N,H,T,D/H)
        value = value.transpose(1,2) # (N,T,H,D/H) -> (N,H,T,D/H)

        #compute dot-product attention separately for each head. Don't forget the scaling value!
        #Expected shape of dot_product is (N, H, S, T)
        """Scale factor = sqrt(embedding dimension)"""
        scale_factor = math.sqrt(D)
        """Attention scores (dot product) = Q_i @ K_i^T"""
        dot_product = query @ key.transpose(-2,-1) # (N,H,S,D/H) @ (N,H,D/H,T) -> (N,H,S,T)
        """Scaled attention scores (scaled dot product) = (Q_i @ K_i^T) / sqrt(embedding dimension)"""
        scaled_attn_scores = dot_product / scale_factor

        if attn_mask is not None:
            """Additive attention mask"""
            big_negative_num = -1e9
            additive_mask = (1 - attn_mask.float()) * big_negative_num
            """Masked scaled attention scores = scaled attention scores + additive mask"""
            scaled_attn_scores += additive_mask
        
        # apply softmax, dropout, and use value
        """Attnetion probabilities = softmax(scaled attention scores)"""
        attn_probs = self.dropout(F.softmax(scaled_attn_scores, dim=-1))
        """Output = attention probabilities @ V"""
        y = attn_probs @ value # (N,H,S,T) @ (N,H,T,D/H) -> (N,H,S,D/H)

        # concat embeddings from different heads, and project
        output = y.transpose(1,2).contiguous().view(N, S, D) # (N,H,S,D/H) -> (N,S,H,D/H) -> (N,S,H*D/H) = (N,S,D)
        return output

class PositionalEncoding(nn.Module):
    def __init__(self, embed_dim, dropout=0.1, max_len=5000):
        super().__init__()
        # TODO - use torch.nn.Embedding to create the encoding. Initialize dropout layer.
        self.encoding = nn.Embedding(num_embeddings=max_len, embedding_dim=embed_dim) # (max_len,D)
        self.dropout = nn.Dropout(p=dropout)
      
    def forward(self, x):
        """
        N: Batch Size
        S: Sequence Length of query
        D: Embedding Dimension
        """
        N, S, D = x.shape

        # TODO - add the encoding to x
        positions = torch.arange(S, dtype=torch.long, device=x.device)
        position_encoded_x = self.encoding(positions) # (S,D)
        output = x + position_encoded_x # (N,S,D) + (N,S,D) -> (N,S,D)
        output = self.dropout(output) # (N,S,D)
        return output

class SelfAttentionBlock(nn.Module):

    def __init__(self, input_dim, num_heads, dropout=0.1):
        super().__init__()
        # TODO: Initialize the following. Use MultiHeadAttentionLayer for self_attn.
        """Multi-head self-attention layer"""
        self.self_attn = MultiHeadAttentionLayer(embed_dim=input_dim, num_heads=num_heads, dropout=dropout)
        """Dropout layer"""
        self.dropout = nn.Dropout(p=dropout)
        """Layer normalization layer"""
        self.layernorm = nn.LayerNorm(normalized_shape=input_dim, elementwise_affine=True)
       
    def forward(self, seq, mask):
        ############# TODO - Self-attention on the sequence, using the mask. Add dropout to attention layer output.
        # Then add a residual connection to the original input, and finally apply normalization. #############################
        """Masked self-attention; Query, key and value are the same"""
        x = self.self_attn(query=seq, key=seq, value=seq, attn_mask=mask) # (N,S,D)
        """Dropout"""
        x = self.dropout(x) # (N,S,D)
        """Residual connection"""
        x = x + seq # (N,S,D) + (N,S,D) -> (N,S,D)
        """Layer normalization"""
        x = self.layernorm(x) # (N,S,D)
        return x

class CrossAttentionBlock(nn.Module):

    def __init__(self, input_dim, num_heads, dropout=0.1):
        super().__init__()
        # TODO: Initialize the following. Use MultiHeadAttentionLayer for cross_attn.
        self.cross_attn = MultiHeadAttentionLayer(embed_dim=input_dim, num_heads=num_heads, dropout=dropout)
        self.dropout = nn.Dropout(p=dropout)
        self.layernorm = nn.LayerNorm(normalized_shape=input_dim, elementwise_affine=True)
       
    def forward(self, seq, cond):
        ############# TODO - Cross-attention on the sequence, using conditioning. Add dropout to attention layer output.
        # Then add a residual connection to the original input, and finally apply normalization. #############################
        """Cross-attention; Query is the sequence, key and value are the conditioning"""
        x = self.cross_attn(query=seq, key=cond, value=cond, attn_mask=None) # (N,S,D)
        """Dropout"""
        x = self.dropout(x) # (N,S,D)
        """Residual connection"""
        x = x + seq # (N,S,D) + (N,S,D) -> (N,S,D)
        """Layer normalization"""
        x = self.layernorm(x) # (N,S,D)
        return x

class FeedForwardBlock(nn.Module):
    def __init__(self, input_dim, dim_feedforward=2048, dropout=0.1):
        super().__init__()
        # TODO: Initialize the following. 
        # MLP has the following layers : linear, relu, dropout, linear; hidden dim of linear is given by dim_feedforward.
        self.mlp = nn.Sequential(nn.Linear(in_features=input_dim, out_features=dim_feedforward, bias=True),
                                nn.ReLU(),
                                nn.Dropout(p=dropout),
                                nn.Linear(in_features=dim_feedforward, out_features=input_dim, bias=True)
                                )
        self.dropout = nn.Dropout(p=dropout)
        self.layernorm = nn.LayerNorm(normalized_shape=input_dim, elementwise_affine=True)
       
    def forward(self, seq):
         ############# TODO - MLP on the sequence. Add dropout to mlp layer output.
        # Then add a residual connection to the original input, and finally apply normalization. #############################
        """Feed-forward"""
        x = self.mlp(seq)
        """Dropout"""
        x = self.dropout(x)
        """Residual connection"""
        x = x + seq
        """Layer normalization"""
        x = self.layernorm(x)
        return x

class DecoderLayer(nn.Module):
    def __init__(self, input_dim, num_heads, dim_feedforward=2048, dropout=0.1 ):
        super().__init__()
        self.self_atn_block = SelfAttentionBlock(input_dim, num_heads, dropout)
        self.cross_atn_block = CrossAttentionBlock(input_dim, num_heads, dropout)
        self.feedforward_block = FeedForwardBlock(input_dim, dim_feedforward, dropout)

    def forward(self, seq, cond, mask):
        out = self.self_atn_block(seq, mask)
        out = self.cross_atn_block(out, cond)
        return self.feedforward_block(out)
       
class TransformerDecoder(nn.Module):
    def __init__(self, word_to_idx, idx_to_word, input_dim, embed_dim, num_heads=4,
                 num_layers=2, max_length=50, device = 'cuda'):
        """
        Construct a new TransformerDecoder instance.
        Inputs:
        - word_to_idx: A dictionary giving the vocabulary. It contains V entries.
          and maps each string to a unique integer in the range [0, V).
        - input_dim: Dimension of input image feature vectors.
        - embed_dim: Embedding dimension of the transformer.
        - num_heads: Number of attention heads.
        - num_layers: Number of transformer layers.
        - max_length: Max possible sequence length.
        """
        super().__init__()

        vocab_size = len(word_to_idx)
        self._null = word_to_idx["<NULL>"]
        self._start = word_to_idx.get("<START>", None)
        self.idx_to_word = idx_to_word
        
        self.layers = nn.ModuleList([DecoderLayer(embed_dim, num_heads) for _ in range(num_layers)])
        
        self.caption_embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=self._null)
        self.positional_encoding = PositionalEncoding(embed_dim, max_len=max_length)
        self.feature_embedding = nn.Linear(input_dim, embed_dim)
        self.score_projection = nn.Linear(embed_dim, vocab_size) 

        self.apply(self._init_weights)
        self.device = device 
        self.to(device)

    def get_data_embeddings(self, features, captions):
        # TODO - get caption and feature embeddings 
        # Don't forget position embeddings for captions!
        # expected caption embedding output shape : (N, T, D)
        feature_embedding = self.feature_embedding(features) # (N,D)
        caption_embedding = self.positional_encoding(self.caption_embedding(captions)) # (N,T,D)

        # Unsqueeze feature embedding along dimension 1
        # expected feature embedding output shape : (N, 1, D) 
        feature_embedding = feature_embedding.unsqueeze(dim=1) # (N,1,D)
        return feature_embedding, caption_embedding

    def get_causal_mask(self, _len):
        #TODO - get causal mask. This should be a matrix of shape (_len, _len). 
        # This mask is multiplicative
        # setting mask[i,j] = 0 means jth element of the sequence is not used 
        # to predict the ith element of the sequence.
        """Causal Mask in Decoder: Lower Triangular Boolean Matrix
        Idea: 
            - Avoid 'cheating' by predicting the ith element of the sequence by using only the elements that come before it.
            - Prevent current element from attending to future elements.
            - Zero out attention score when j (column) > i (row) in attention score matrix (square) of shape (S,S) where S is the target sequence length.
        Ref1: https://pi-tau.github.io/posts/transformer/#decoder-block
        Ref2: https://ai.stackexchange.com/questions/41508/confusion-about-triangle-mask-in-transformer-decoder
        Ref3: https://ai.stackexchange.com/questions/42116/transformer-decoder-causal-masking-during-inference"""
        mask = torch.ones(_len, _len, dtype=torch.bool).tril(diagonal=0).to(self.device)
        return mask
                                      
    def forward(self, features, captions):
        """
        Given image features and caption tokens, return a distribution over the
        possible tokens for each timestep. Note that since the entire sequence
        of captions is provided all at once, we mask out future timesteps.
        Inputs:
         - features: image features, of shape (N, D)
         - captions: ground truth captions, of shape (N, T)
        Returns:
         - scores: score for each token at each timestep, of shape (N, T, V)
        """
        features_embed, captions_embed = self.get_data_embeddings(features, captions)
        mask = self.get_causal_mask(captions_embed.shape[1])
        mask.to(captions_embed.dtype)
        
        output = captions_embed
        for layer in self.layers:
            output = layer(output, features_embed, mask=mask)

        scores = self.score_projection(output)
        return scores

    def _init_weights(self, module):
        if isinstance(module, (nn.Linear, nn.Embedding)):
            module.weight.data.normal_(mean=0.0, std=0.02)
            if isinstance(module, nn.Linear) and module.bias is not None:
                module.bias.data.zero_()
        elif isinstance(module, nn.LayerNorm):
            module.bias.data.zero_()
            module.weight.data.fill_(1.0)

    def sample(self, features, max_length=30):
        """
        Given image features, use greedy decoding to predict the image caption.
        Inputs:
         - features: image features, of shape (N, D)
         - max_length: maximum possible caption length
        Returns:
         - captions: captions for each example, of shape (N, max_length)
        """
        with torch.no_grad():
            features = torch.Tensor(features).to(self.device)
            N = features.shape[0]

            # Create an empty captions tensor (where all tokens are NULL).
            captions = self._null * np.ones((N, max_length), dtype=np.int32)

            # Create a partial caption, with only the start token.
            partial_caption = self._start * np.ones(N, dtype=np.int32)
            partial_caption = torch.LongTensor(partial_caption).to(self.device)
            # [N] -> [N, 1]
            partial_caption = partial_caption.unsqueeze(1)

            for t in range(max_length):

                # Predict the next token (ignoring all other time steps).
                output_logits = self.forward(features, partial_caption)
                output_logits = output_logits[:, -1, :]

                # Choose the most likely word ID from the vocabulary.
                # [N, V] -> [N]
                word = torch.argmax(output_logits, axis=1)

                # Update our overall caption and our current partial caption.
                captions[:, t] = word.cpu().numpy()
                word = word.unsqueeze(1)
                partial_caption = torch.cat([partial_caption, word], dim=1)

            return captions



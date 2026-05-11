import torch
import torch.nn as nn
import types

# 這是我們要用來替換原始 forward 的「間諜函數」
def forward_with_spy(self,
                     target,
                     reference_points,
                     value,
                     spatial_shapes,
                     attn_mask=None,
                     query_pos_embed=None):
    
    # 1. Self Attention 前置處理 (保持原樣)
    q = k = self.with_pos_embed(target, query_pos_embed)

    # 2. 【關鍵修改】強制拿取 weights 並存起來
    # 原本是: target2, _ = self.self_attn(...)
    # 我們改成:
    target2, attn_weights = self.self_attn(
        q, k, value=target, 
        attn_mask=attn_mask,
        need_weights=True,          # 強制要求回傳權重
        average_attn_weights=False  #我們要看每個 Head 的細節，不要平均
    )
    
    # 3. 把權重偷存到 layer 物件身上
    # 之後你可以透過 model.decoder.layers[i].last_attn_weights 讀取
    self.last_attn_weights = attn_weights.detach().cpu()

    # 4. 後續流程 (保持原樣，複製貼上即可)
    target = target + self.dropout1(target2)
    target = self.norm1(target)

    # cross attention
    target2 = self.cross_attn(
        self.with_pos_embed(target, query_pos_embed),
        reference_points,
        value,
        spatial_shapes
    )

    if self.use_gateway:
        target = self.gateway(target, self.dropout2(target2))
    else:
        target = target + self.dropout2(target2)
        target = self.norm2(target)

    # ffn
    target2 = self.swish_ffn(target)
    target = target + self.dropout4(target2)
    target = self.norm3(target.clamp(min=-65504, max=65504))

    return target
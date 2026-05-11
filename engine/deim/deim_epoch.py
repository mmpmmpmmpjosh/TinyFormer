"""
Copyright (c) 2024 The DEIM Authors. All Rights Reserved.
"""

import torch.nn as nn
from ..core import register


__all__ = ['DEIM', ]


@register()
class DEIM(nn.Module):
    __inject__ = ['backbone', 'encoder', 'decoder', ]

    def __init__(self, \
        backbone: nn.Module,
        encoder: nn.Module,
        decoder: nn.Module,
    ):
        super().__init__()
        self.backbone = backbone
        self.decoder = decoder
        self.encoder = encoder

    # [FIX] 新增 epoch 參數，預設為 0 (驗證時通常不傳或是傳 0)
    def forward(self, x, targets=None, epoch=0):
        x = self.backbone(x)
        x = self.encoder(x)
        
        # [FIX] 將 epoch 傳遞給 decoder (DEIMTransformer)
        x = self.decoder(x, targets, epoch=epoch)

        return x

    def deploy(self, ):
        self.eval()
        for m in self.modules():
            if hasattr(m, 'convert_to_deploy'):
                m.convert_to_deploy()
        return self
"""
DEIMv2: Real-Time Object Detection Meets DINOv3
Copyright (c) 2025 The DEIMv2 Authors. All Rights Reserved.
---------------------------------------------------------------------------------
Modified from DINOv3 (https://github.com/facebookresearch/dinov3)

Copyright (c) Meta Platforms, Inc. and affiliates.

This software may be used and distributed in accordance with
the terms of the DINOv3 License Agreement.
---------------------------------------------------------------------------------
TinyFormer: Preserving Tiny Objects in YOLO-style Detectors
Copyright (c) 2026 TinyFormer Authors. All Rights Reserved.
"""
import os
import torch
import torch.nn as nn
import torch.nn.functional as F
from ..core import register
from .vit_tiny import VisionTransformer
from .dinov3 import DinoVisionTransformer


class SpatialSemanticAdapter(nn.Module):
    def __init__(self, inplanes=16):
        super().__init__()
        # 1/2 -> 1/4
        self.stem = nn.Sequential(
            nn.Conv2d(3, inplanes, kernel_size=3, stride=2, padding=1, bias=False),
            nn.SyncBatchNorm(inplanes),
            nn.GELU(),
            # MaxPool -> Stride Conv
            nn.Conv2d(inplanes, inplanes, kernel_size=3, stride=2, padding=1, bias=False),
            nn.SyncBatchNorm(inplanes),
            nn.GELU(),
        )
        # 1/4 -> 1/8
        self.conv2 = nn.Sequential(
            nn.Conv2d(inplanes, 2 * inplanes, kernel_size=3, stride=2, padding=1, bias=False),
            nn.SyncBatchNorm(2 * inplanes),
            nn.GELU()
        )
        self.out_channels = 2 * inplanes 

    def forward(self, x):
        x = self.stem(x)
        x = self.conv2(x)
        return x

@register()
class DINOv3SSAs(nn.Module):
    def __init__(
        self,
        name=None,
        weights_path=None,
        interaction_indexes=[], 
        finetune=True,
        embed_dim=192,
        num_heads=3,
        patch_size=16,
        use_adapter=True,
        conv_inplane=16,
        hidden_dim=None, 
    ):
        super(DINOv3SSAs, self).__init__()
        
        # --- DINO Init ---
        if 'dinov3' in name:
            self.dinov3 = DinoVisionTransformer(name=name)
            if weights_path is not None and os.path.exists(weights_path):
                print(f'Loading ckpt from {weights_path}...')
                self.dinov3.load_state_dict(torch.load(weights_path))
        else:
            self.dinov3 = VisionTransformer(embed_dim=embed_dim, num_heads=num_heads, return_layers=interaction_indexes)
            if weights_path is not None and os.path.exists(weights_path):
                print(f'Loading ckpt from {weights_path}...')
                self.dinov3._model.load_state_dict(torch.load(weights_path))

        embed_dim = self.dinov3.embed_dim
        self.interaction_indexes = interaction_indexes
        
        if not finetune:
            self.dinov3.eval()
            self.dinov3.requires_grad_(False)


        self.use_sda = use_adapter
        if use_adapter:
            self.sda = SpatialSemanticAdapter(inplanes=conv_inplane)
            sda_dim = self.sda.out_channels
        else:
            sda_dim = 0

        hidden_dim = hidden_dim if hidden_dim is not None else embed_dim

        
        
        
        self.proj_c2 = nn.Sequential(
            nn.Conv2d(sda_dim + embed_dim, hidden_dim, 1, bias=False),
            nn.SyncBatchNorm(hidden_dim),
            nn.GELU() 
        )

        # C3 (1/16): DINO_L1(1/16) -> hidden_dim
        self.proj_c3 = nn.Sequential(
            nn.Conv2d(embed_dim, hidden_dim, 1, bias=False),
            nn.SyncBatchNorm(hidden_dim),
        )

        
        self.proj_c4 = nn.Sequential(
            nn.Conv2d(embed_dim, hidden_dim, 3, stride=2, padding=1, bias=False),
            nn.SyncBatchNorm(hidden_dim),
            # nn.GELU() 
        )

    def forward(self, x):
        B, C, H, W = x.shape
        H_16, W_16 = H // 16, W // 16 

        
        if len(self.interaction_indexes) > 0 and not isinstance(self.dinov3, VisionTransformer):
            all_layers = self.dinov3.get_intermediate_layers(
                x, n=self.interaction_indexes, return_class_token=True
            )
        else:
            all_layers = self.dinov3(x)

        if len(all_layers) == 1:
            l0, l1, l2 = all_layers[0], all_layers[0], all_layers[0]
        else:
            l0, l1, l2 = all_layers[0], all_layers[1], all_layers[2]

        feat0 = l0[0].transpose(1, 2).view(B, -1, H_16, W_16).contiguous()
        feat1 = l1[0].transpose(1, 2).view(B, -1, H_16, W_16).contiguous()
        feat2 = l2[0].transpose(1, 2).view(B, -1, H_16, W_16).contiguous()

        
        if self.use_sda:
            sda_feat = self.sda(x) 
        else:
            sda_feat = None

       
        target_h8, target_w8 = sda_feat.shape[2:]
        feat0_up = F.interpolate(feat0, size=(target_h8, target_w8), mode='bilinear', align_corners=False)
        
        if self.use_sda:
            c2_in = torch.cat([sda_feat, feat0_up], dim=1) 
        else:
            c2_in = feat0_up
            
        c2 = self.proj_c2(c2_in)

        
        c3 = self.proj_c3(feat1)

        
        c4 = self.proj_c4(feat2)

        return c2, c3, c4
    

@register()
class DINOv3SSAs_4Scale(nn.Module):
    def __init__(
        self,
        name=None,
        weights_path=None,
        interaction_indexes=[], 
        finetune=True,
        embed_dim=192,
        num_heads=3,
        patch_size=16,
        use_adapter=True,
        conv_inplane=16,
        hidden_dim=None, 
    ):
        super().__init__()
        
        # --- DINO Init ---
        if 'dinov3' in name:
            self.dinov3 = DinoVisionTransformer(name=name)
            if weights_path is not None and os.path.exists(weights_path):
                self.dinov3.load_state_dict(torch.load(weights_path))
        else:
            self.dinov3 = VisionTransformer(embed_dim=embed_dim, num_heads=num_heads, return_layers=interaction_indexes)
            if weights_path is not None and os.path.exists(weights_path):
                self.dinov3._model.load_state_dict(torch.load(weights_path))

        embed_dim = self.dinov3.embed_dim
        self.interaction_indexes = interaction_indexes
        
        if not finetune:
            self.dinov3.eval()
            self.dinov3.requires_grad_(False)


        self.use_sda = use_adapter
        if use_adapter:
            self.sda = nn.Sequential(
                # 1/2
                nn.Sequential(
                    nn.Conv2d(3, conv_inplane, 3, 2, 1, bias=False),
                    nn.SyncBatchNorm(conv_inplane),
                    nn.GELU()
                ),
                # 1/4
                nn.Sequential(
                    nn.Conv2d(conv_inplane, conv_inplane, 3, 2, 1, bias=False),
                    nn.SyncBatchNorm(conv_inplane),
                    nn.GELU()
                ),
                # 1/8
                nn.Sequential(
                    nn.Conv2d(conv_inplane, 2 * conv_inplane, 3, 2, 1, bias=False),
                    nn.SyncBatchNorm(2 * conv_inplane),
                    nn.GELU()
                )
            )
            
            c1_dim = conv_inplane
            sda_dim = 2 * conv_inplane
        else:
            c1_dim = conv_inplane
            sda_dim = 0

        hidden_dim = hidden_dim if hidden_dim is not None else embed_dim


        self.proj_c1 = nn.Sequential(
            nn.Conv2d(c1_dim, hidden_dim, 1, bias=False),
            nn.SyncBatchNorm(hidden_dim),
            nn.GELU() 
        )


        self.proj_c2 = nn.Sequential(
            nn.Conv2d(sda_dim + embed_dim, hidden_dim, 1, bias=False),
            nn.SyncBatchNorm(hidden_dim),
            nn.GELU() 
        )


        self.proj_c3 = nn.Sequential(
            nn.Conv2d(embed_dim, hidden_dim, 1, bias=False),
            nn.SyncBatchNorm(hidden_dim),
        )


        self.proj_c4 = nn.Sequential(
            nn.Conv2d(embed_dim, hidden_dim, 1, bias=False),
            nn.SyncBatchNorm(hidden_dim),
        )

    def forward(self, x):
        B, C, H, W = x.shape
        H_16, W_16 = H // 16, W // 16 

        # 1. DINO Feats
        if len(self.interaction_indexes) > 0 and not isinstance(self.dinov3, VisionTransformer):
            all_layers = self.dinov3.get_intermediate_layers(x, n=self.interaction_indexes, return_class_token=True)
        else:
            all_layers = self.dinov3(x)

        if len(all_layers) == 1:
            l0, l1, l2 = all_layers[0], all_layers[0], all_layers[0]
        else:
            l0, l1, l2 = all_layers[0], all_layers[1], all_layers[2]

        feat0 = l0[0].transpose(1, 2).view(B, -1, H_16, W_16).contiguous()
        feat1 = l1[0].transpose(1, 2).view(B, -1, H_16, W_16).contiguous()
        feat2 = l2[0].transpose(1, 2).view(B, -1, H_16, W_16).contiguous()


        c1_sda, c2_sda = None, None
        if self.use_sda:

            s_1_2 = self.sda[0](x)
            s_1_4 = self.sda[1](s_1_2) # C1 source
            s_1_8 = self.sda[2](s_1_4) # C2 source
            
            c1_sda = s_1_4
            c2_sda = s_1_8

        if self.use_sda:
            c1 = self.proj_c1(c1_sda)
        else:
            c1 = self.proj_c1(F.interpolate(feat0, scale_factor=4.0, mode='bilinear'))


        target_h8, target_w8 = (H // 8, W // 8)
        if c2_sda is not None:
             target_h8, target_w8 = c2_sda.shape[2:]
             
        feat0_up = F.interpolate(feat0, size=(target_h8, target_w8), mode='bilinear', align_corners=False)
        
        if self.use_sda:
            c2_in = torch.cat([c2_sda, feat0_up], dim=1) 
        else:
            c2_in = feat0_up
        c2 = self.proj_c2(c2_in)


        c3 = self.proj_c3(feat1)


        feat2_down = F.interpolate(feat2, scale_factor=0.5, mode='bilinear', align_corners=False)
        c4 = self.proj_c4(feat2_down)

        return c1, c2, c3, c4
"""Model factory (ROADMAP M4.1): build(arch, encoder|backbone, init, in_channels, freeze_encoder).

Sources: segmentation-models-pytorch, TorchGeo weights (SSL4EO-S12), TerraTorch GFMs.
Missing pretrained input channels are zero-initialised and the fact is logged.
"""

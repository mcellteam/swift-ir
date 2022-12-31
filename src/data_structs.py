#!/usr/bin/env python3
import src.config as cfg

data_template = \
    {
        "version": 0.50,
        "method": "None",
        "user_settings": {
            "max_image_file_size": 100000000,
            "use_c_version": True
        },
        "data": {
            "source_path": "",
            "destination_path": "",
            "current_layer": 0,
            "current_scale": "scale_1",
            "panel_roles": [
                "ref",
                "base",
                "aligned"
            ],
            "thumbnails": [],
            "scales": {
                "scale_1": {
                    "method_data": {
                        "alignment_option": "init_affine"
                    },
                    "null_cafm_trends": cfg.DEFAULT_NULL_BIAS,
                    "use_bounding_rect": cfg.DEFAULT_BOUNDING_BOX,
                    "alignment_stack": []
                }
            }
        }
    }
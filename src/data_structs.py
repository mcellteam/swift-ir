#!/usr/bin/env python3
import src.config as cfg

data_template = \
    {
        "version": 0.50,
        "created": '',
        "method": "None",
        "user_settings": {
            "use_c_version": True
        },
        "data": {
            "source_path": "",
            "destination_path": "",
            "current_layer": 0,
            "current_scale": "scale_1",
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

layer_template = \
    {
        "align_to_ref_method": {
            "method_data": {},
            "method_options": {},
            "selected_method": "Auto Swim Align",
            "match_points": {
                "src": [],
                'ref': []
            },
            "method_results": {}
        },
        "images": {},
        "skipped": False
    }

image_template = \
    {
        "filename": None,
        "metadata": {
            "annotations": [],
            "match_points": []
        }
    }

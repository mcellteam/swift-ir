#!/usr/bin/env python3
import src.config as cfg

data_template = \
    {
        "version": 0.50,
        "created": '',
        "system": {
            "node": None,
        },
        "state": {
            "mode": "comparison",
            "previous_mode": None,
            "manual_mode": True,
            "ng_layout": 'xy',
            "stage_viewer": {
                "show_yellow_frame": True
            },
        },
        "rendering": {
            "normalize": [1,255],
            "brightness": 0,
            "contrast": 0,
        },
        "data": {
            "defaults": {},
            "shader": None,
            "source_path": "",
            "destination_path": "",
            "z_position": 0,
            "current_scale": "scale_1",
            "thumb_scaling_factor_source": None,
            "scales": {
                "scale_1": {
                    "method_data": {
                        "alignment_option": "init_affine"
                    },
                    "use_bounding_rect": cfg.DEFAULT_BOUNDING_BOX,
                    "stack": [],
                    "thumb_scaling_factor_aligned": None,
                    "thumb_scaling_factor_corr_spot": None,
                }
            },
        },

    }

layer_template = \
    {
        "alignment": {
            "manual_settings": {},
            "method_data": {},
            "method_options": {},
            "manpoints": {
                "ref": [],
                'base': []
            },
            "method_results": {
                "snr": [],
                "snr_prev": [],
            }
        },
        "images": {},
        "skipped": False,
        "notes": ""
    }

image_template = \
    {
        "filename": None,
        "metadata": {
            "annotations": [],
            "manpoints": []
        }
    }

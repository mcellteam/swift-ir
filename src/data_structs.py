#!/usr/bin/env python3
import src.config as cfg

data_template = \
    {
        "version": None,
        "created": '',
        "system": {
            "node": None,
        },
        "state": {
            "mode": "comparison",
            "manual_mode": False,
            "ng_layout": 'xy',
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
                    "use_bounding_rect": cfg.DEFAULT_BOUNDING_BOX,
                    "stack": [],
                }
            },
        },

    }

layer_template = \
    {
        "alignment": {
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

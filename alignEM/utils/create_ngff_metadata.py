#!/usr/bin/env python3

AXES_TYPE_DICT = {
    "x": "space",
    "y": "space",
    "z": "space",
    "t": "time",
    "c": "channel"
}

def create_ngff_metadata(g, name, axes_names, scale=None, units=None, type_=None,
                         metadata=None, time_scale=None, prefix=None):

    # axes metadata
    axes = [
        {"name": name, "type": AXES_TYPE_DICT[name]} for name in axes_names
    ]
    if units is not None:
        assert len(units) == len(axes_names)
        for ax, unit in zip(axes, units):
            if unit is not None:
                ax["unit"] = unit

    # dataset metadata including transformations
    spatial_dims = [i for i, ax in enumerate(axes_names) if ax in "xyz"]
    if scale is None:
        scale = [1.0] * len(spatial_dims)
    else:
        scale = [scale[ax] for ax in axes_names if ax in "xyz"]

    # TODO read this from the downscaling args
    scale_factor = 2

    ds_root = g if prefix is None else g[prefix]

    # NOTE we might need a half pixel offset for proper scale alignment here (via a translation)
    n_non_spatial = len(axes_names) - len(spatial_dims)
    transforms = [
        [{"type": "scale", "scale": [1] * n_non_spatial + [sc * scale_factor**i for sc in scale]}]
        for i in range(len(ds_root))
    ]
    datasets = [
        {"path": name if prefix is None else f"{prefix}/{name}", "coordinateTransformations": trafo}
        for name, trafo in zip(ds_root, transforms)
    ]

    ms_entry = {
        "axes": axes,
        "datasets": datasets,
        "name": name,
        "version": "0.4"
    }
    if type_ is not None:
        ms_entry["type"] = type_
    if metadata is not None:
        ms_entry["metadata"] = metadata

    if time_scale is None:
        transforms = None
    else:
        scale = [time_scale if ax == "t" else 1 for ax in axes_names]
        transforms = [{"type": "scale", "scale": scale}]
    if transforms is not None:
        ms_entry["coordinateTransformations"] = transforms

    metadata = g.attrs.get("multiscales", [])
    metadata.append(ms_entry)
    g.attrs["multiscales"] = metadata

    # write the array dimensions for compat with xarray:
    # https://xarray.pydata.org/en/stable/internals/zarr-encoding-spec.html?highlight=zarr
    for ds in g.values():
        ds.attrs["_ARRAY_DIMENSIONS"] = axes_names


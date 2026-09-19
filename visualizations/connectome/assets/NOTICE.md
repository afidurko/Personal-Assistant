# Third-party notices — Cam cortex mesh assets

## cam-cortex.glb

Derived from FreeSurfer Desikan–Killiany cortical and subcortical meshes
distributed as **Brain for Blender** by Anderson M. Winkler (Brainder.org).

- Source: https://brainder.org/research/brain-for-blender/
- License: Creative Commons Attribution-ShareAlike 3.0 Unported (CC BY-SA 3.0)
  https://creativecommons.org/licenses/by-sa/3.0/
- Atlas: Desikan RS et al. (2006). NeuroImage 31(3):968–980.
  DOI: 10.1016/j.neuroimage.2006.01.021
- Build tool: freesurfer-to-glb (Apache-2.0 code) with Cam region map
  `config/connectome/anatomy-region-map.json`

Regenerate:

```bash
# Node 22 may need the navigator polyfill patched in freesurfer-to-glb
npx freesurfer-to-glb \
  --region-map config/connectome/anatomy-region-map.json \
  --output visualizations/connectome/assets/cam-cortex.glb \
  --cache /tmp/cam-brain-meshes \
  --radius 2.4
```

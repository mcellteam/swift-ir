echo ========== Swim Second ==========

./swim 1024 <<'EOF'
unused -i 2 -x 500 -y 500 vj_097_shift_rot_skew_crop_1.jpg 403 390 vj_097_shift_rot_skew_crop_2.jpg 477.8 305.984
unused -i 2 -x 500 -y -500 vj_097_shift_rot_skew_crop_1.jpg 403 390 vj_097_shift_rot_skew_crop_2.jpg 477.8 305.984
unused -i 2 -x -500 -y -500 vj_097_shift_rot_skew_crop_1.jpg 403 390 vj_097_shift_rot_skew_crop_2.jpg 477.8 305.984
unused -i 2 -x -500 -y 500 vj_097_shift_rot_skew_crop_1.jpg 403 390 vj_097_shift_rot_skew_crop_2.jpg 477.8 305.984
EOF


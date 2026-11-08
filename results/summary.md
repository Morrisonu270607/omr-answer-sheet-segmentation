# Experiment summary

Test split only; parameters selected on the validation split.

| Method | Pixel F1 | Bubble F1 | Answer Acc. | Time (ms) |
|---|---:|---:|---:|---:|
| 基线：全局 Otsu + 连通域 | 0.2705 | 0.3673 | 0.6917 | 88.5 |
| 对照：全局 Otsu + 选项区域覆盖率 | 0.7865 | 0.7229 | 0.8333 | 10.4 |
| 改进：局部自适应 + 形态学 + 覆盖率 | 1.0000 | 1.0000 | 1.0000 | 98.6 |

## Per group (bubble F1 / answer accuracy)

| Method | clean | light | hard |
|---|---:|---:|---:|
| 基线：全局 Otsu + 连通域 | 0.400 / 1.000 | 0.410 / 0.850 | 0.209 / 0.225 |
| 对照：全局 Otsu + 选项区域覆盖率 | 1.000 / 1.000 | 0.842 / 1.000 | 0.510 / 0.500 |
| 改进：局部自适应 + 形态学 + 覆盖率 | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 |

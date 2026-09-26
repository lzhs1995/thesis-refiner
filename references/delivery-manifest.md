# 从冻结清单生成交付链接

成品已存在时使用`scripts/delivery_manifest.py`。它核清单、目录完整文件集合、角色、后缀、SHA256和大小，可选核源文件映射及ZIP全成员CRC；输出能直接复制到聊天的绝对链接。它不修改或重封成品，不执行Office、NLM或音频，不替代科学、视觉和听审。

清单是有哈希的JSON，`files`为非空数组，每项有`package_path`（精确POSIX相对名）、`sha256`、整数`bytes`。可选`source`是原件的绝对路径/SHA引用。旧清单使用`name`或相对`path`时，在旁置合同指定`member_field`；不改冻结清单。其他历史形状需要显式转换为新的旁置清单并保留来源绑定，不能猜测前缀。

```json
{
  "schema": "delivery-manifest-v1",
  "package_root": "/absolute/delivery/final-package",
  "manifest": {"path": "/absolute/delivery/final-package/MANIFEST.json", "sha256": "<actual-sha256>"},
  "roles": [
    {"id": "slides", "member": "slides/final.pptx", "label": "答辩PPT", "suffixes": [".pptx"]},
    {"id": "speech", "member": "audio/rehearsal.m4a", "label": "演练音频", "suffixes": [".m4a"]}
  ],
  "zip": {
    "file": {"path": "/absolute/delivery/final-package.zip", "sha256": "<actual-sha256>"},
    "prefix": "final-package/",
    "label": "完整ZIP",
    "role": "archive"
  }
}
```

ZIP带顶层目录时显式写含末尾`/`的`prefix`，无顶层时写`""`。不按basename或模糊suffix找成员。重复成员、额外文件、错前缀、路径逃逸、加密/符号链接成员和CRC/大小/SHA错误均失败。包内清单自身不列在`files`中，由检查器按原字节加入集合；包外旁置清单不加入ZIP。空目录只能是已声明文件的祖先。

要在聊天中交付包外ZIP，显式提供`zip.label`；检查器在完整核验后追加该ZIP的绝对链接，`zip.role`默认`archive`且不能与包内角色重复，文件须为`.zip`后缀。省略标签时保留旧行为，只报告ZIP核验。包外ZIP不塞进包内`roles`或成员清单，也不参与自身成员集合。

`require_sources: true`要求每项都有`source`引用；默认只核已提供的映射并报告条数。角色是作者声明，本工具核文件身份和后缀，不能判断某PDF是否真是逐字稿。音频解码、文本绑定、时长和逐句听审各自记录。

```bash
python3 scripts/delivery_manifest.py \
  --contract /absolute/run/delivery-links-contract.json \
  --output /absolute/run/delivery-links-result.json \
  --markdown-output /absolute/run/delivery-links.md
```

报告须使用包外尚不存在的绝对路径。保留原失败，修复旁置合同后用新报告路径重试。聊天采用生成的`markdown`，不重新手写文件夹或扩展名。

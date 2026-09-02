# Dataset Overlap Audit

## Cross-Source Overlap

Strong overlaps are based on normalized repository URL or DOI. Name-only matches
are diagnostics and must not be treated as exact duplicates without manual
review.

| key_type | key_value | match_strength | papers_with_code_records | biotools_records | total_records |
| --- | --- | --- | --- | --- | --- |
| normalized_name | disco | ambiguous_name_only | 30 | 5 | 35 |
| normalized_name | star | ambiguous_name_only | 25 | 5 | 30 |
| normalized_name | comet | ambiguous_name_only | 22 | 6 | 28 |
| normalized_name | code | ambiguous_name_only | 27 | 1 | 28 |
| normalized_name | cat | ambiguous_name_only | 25 | 1 | 26 |
| normalized_name | scope | ambiguous_name_only | 11 | 14 | 25 |
| normalized_name | scenic | ambiguous_name_only | 23 | 1 | 24 |
| normalized_name | sockeye | ambiguous_name_only | 20 | 1 | 21 |
| normalized_name | mars | ambiguous_name_only | 19 | 2 | 21 |
| normalized_name | core | ambiguous_name_only | 18 | 2 | 20 |
| normalized_name | adapt | ambiguous_name_only | 19 | 1 | 20 |
| normalized_name | ace | ambiguous_name_only | 16 | 4 | 20 |
| normalized_name | cola | ambiguous_name_only | 18 | 1 | 19 |
| normalized_name | vista | ambiguous_name_only | 10 | 8 | 18 |
| normalized_name | sam | ambiguous_name_only | 14 | 3 | 17 |
| normalized_name | dream | ambiguous_name_only | 15 | 2 | 17 |
| normalized_name | gem | ambiguous_name_only | 13 | 4 | 17 |
| normalized_name | laser | ambiguous_name_only | 16 | 1 | 17 |
| normalized_name | flare | ambiguous_name_only | 12 | 4 | 16 |
| normalized_name | craft | ambiguous_name_only | 13 | 3 | 16 |
| normalized_name | mega | ambiguous_name_only | 4 | 12 | 16 |
| normalized_name | hydra | ambiguous_name_only | 12 | 3 | 15 |
| normalized_name | lisa | ambiguous_name_only | 14 | 1 | 15 |
| normalized_name | flower | ambiguous_name_only | 14 | 1 | 15 |
| normalized_name | dan | ambiguous_name_only | 12 | 3 | 15 |
| normalized_name | eva | ambiguous_name_only | 13 | 2 | 15 |
| normalized_name | sst | ambiguous_name_only | 14 | 1 | 15 |
| normalized_name | falcon | ambiguous_name_only | 13 | 2 | 15 |
| normalized_name | space | ambiguous_name_only | 9 | 6 | 15 |
| normalized_name | prism | ambiguous_name_only | 9 | 6 | 15 |
| normalized_name | magic | ambiguous_name_only | 11 | 4 | 15 |
| normalized_name | care | ambiguous_name_only | 14 | 1 | 15 |
| normalized_name | mist | ambiguous_name_only | 12 | 2 | 14 |
| normalized_name | magnet | ambiguous_name_only | 13 | 1 | 14 |
| normalized_name | hint | ambiguous_name_only | 13 | 1 | 14 |
| normalized_name | trace | ambiguous_name_only | 13 | 1 | 14 |
| normalized_name | seal | ambiguous_name_only | 12 | 2 | 14 |
| normalized_name | dig | ambiguous_name_only | 13 | 1 | 14 |
| normalized_name | san | ambiguous_name_only | 12 | 1 | 13 |
| normalized_name | fusion | ambiguous_name_only | 11 | 2 | 13 |
| normalized_name | ssp | ambiguous_name_only | 10 | 3 | 13 |
| normalized_name | atlas | ambiguous_name_only | 8 | 5 | 13 |
| normalized_name | arc | ambiguous_name_only | 11 | 2 | 13 |
| normalized_name | sage | ambiguous_name_only | 11 | 2 | 13 |
| normalized_name | eagle | ambiguous_name_only | 8 | 5 | 13 |
| normalized_name | gan | ambiguous_name_only | 11 | 1 | 12 |
| normalized_name | vision | ambiguous_name_only | 11 | 1 | 12 |
| normalized_name | tap | ambiguous_name_only | 8 | 4 | 12 |
| normalized_name | cape | ambiguous_name_only | 11 | 1 | 12 |
| normalized_name | grasp | ambiguous_name_only | 10 | 2 | 12 |

## Duplicate Keys

Duplicate identifiers and repeated repositories/publications are expected in
some places because source observations are not identical to software packages.
They are reported here rather than removed.

| source | key_type | key_value | record_count | examples |
| --- | --- | --- | --- | --- |
| bio.tools | doi | 10.1038/nmeth.3252 | 386 | 9d30c7355a8a2c3a3bba1645 | 089aabdd06637c5f76a0f0eb | a6021f21b196ae1b36629d74 |
| bio.tools | doi | 10.7490/f1000research.1114334.1 | 305 | 0cf536f40aa991d55d8fb706 | 9bc57530ed35264910b3a84b | fcf8c41497867c04012db10a |
| bio.tools | doi | 10.1016/s0168-9525(00)02024-2 | 284 | b39af92dcb0916758bdef524 | c135a962d5866ce3ad71decc | d20c813750dce3ade3f7040d |
| bio.tools | doi | 10.1093/nar/gkw343 | 279 | 8b6237733a11aea1f8670399 | 504acd14969dad54511da700 | 30a674a4db9246c80c28e5d9 |
| bio.tools | doi | 10.1017/cbo9781139151399 | 256 | 6ec492ed2b3d7804868a3deb | 8acc3e601bfdce222da39dbd | 8fa6ce1e5789bcb3acc1d8ab |
| bio.tools | doi | 10.1017/cbo9781139151405 | 256 | c36344aaeb53be3701b9f9dc | df8c2eb0f9268f70e6da061e | 0709f4bb7b2985af9aecc84b |
| bio.tools | doi | 10.1093/nar/gkac240 | 66 | 1a0c654d5f5ae04d469bc026 | 14f554c619489e29d9754a8b | 18fafd169268bfdeefcd46f5 |
| bio.tools | doi | 10.1093/nar/gkae241 | 47 | 4dab29fe6d53a7d1bed411ad | ebd8de8088d6f4ca49702c88 | 90e6be7a36908ad67861c56d |
| bio.tools | doi | 10.1093/bioinformatics/bts577 | 34 | 06f70e67933c499181fd367a | 4919e0d63ae63dbffac9e2a3 | 00cc220d8a89ab00ad1f91c0 |
| bio.tools | doi | 10.7554/elife.07009 | 24 | fd581d37fea241845765226a | 8d996e9b3a7143e0aa9427c3 | b8547963c32b44c1cf8a13e4 |
| bio.tools | doi | 10.1093/nar/gkv1157 | 22 | 92c93b3de92ce590f1501333 | 72529c18cd70781248749523 | e483189222fdc4d6d8b0f3b8 |
| bio.tools | doi | 10.1093/nar/gku1056 | 21 | 11899128b9a1f5bcf6efcd6b | 3125fed3793838ec767f8ae3 | 437211db09193dfa32dfca4b |
| bio.tools | doi | 10.1038/s41597-019-0177-4 | 19 | c2dc55633a84d8599820af68 | b119468b9522aee9b5880780 | e68a8d4df32ab353047c3a9b |
| bio.tools | doi | 10.1093/nar/gkv1352 | 18 | 8a31ba6ccde2ed663a174e8c | f4bb0ab05f2c136ce8e2550b | 0b53bbb8bedfd2be33d1703a |
| bio.tools | doi | 10.1093/nar/gkr367 | 12 | f2feffde88ab0fff68f58756 | 74d110c045a1307a34270e14 | 50fc6d421f2b38a4892b08e5 |
| bio.tools | doi | 10.1186/1471-2164-15-1039 | 12 | 6aeb83d3cb5690c1c4a99a1e | dddcc77140e2c1100b657efa | d7270ef6127664759833abb9 |
| bio.tools | doi | 10.1093/bioinformatics/btp352 | 11 | 281b5c73f3f7c616705420dc | af9b4f8cbaf08c8f42573587 | 82d977fc1db8a0f8b75caf1e |
| bio.tools | doi | 10.1038/s41587-020-0439-x | 10 | 8f5ef674456c38ac06b863e3 | b7ae7ec5dc58e03864b69838 | 070038a712c4ebd16315159f |
| bio.tools | doi | 10.1016/s0022-2836(05)80360-2 | 10 | 3d91226bf3005f318a2f9758 | 0f828b57695295b1cfdc470c | 6cbd075d8da617208921e0b3 |
| bio.tools | doi | 10.1093/bioinformatics/btt100 | 10 | d09ca57ffe84776ec1422726 | 17c75ce30c79a7ffc4eaf271 | 735dfe6d558c1f3869f925fe |
| bio.tools | doi | 10.1093/bioinformatics/btr304 | 10 | fe7ed5dc1de0e49d76ac410c | c3e44883149792ab51cc1936 | 6f22bb67ef9f166d8ae4e7d8 |
| bio.tools | doi | 10.1186/1471-2164-15-264 | 10 | 7f768648d47bd626abaceaec | 02bb87a6f962f1a7988df0de | abe338c33be33479351c795e |
| bio.tools | doi | 10.1186/1471-2105-14-184 | 9 | 07413d0b741ca098a986c986 | 117f9c61d1ae9635a89fee84 | 0b6864b30e6b692982dfdc32 |
| bio.tools | doi | 10.1038/ng.806 | 9 | dd06780f3fec54bd2847a1c9 | a4ca03ff6b271ac1aa3a4ca3 | bf7d70e604cdb0ef22e11b6b |
| bio.tools | doi | 10.1093/bioinformatics/bts311 | 8 | 1d9899c238a72ab34a7927dd | f5c63b43a9238007a9e562d6 | ad31a1768289adf3cc46a91c |
| bio.tools | doi | 10.1186/1471-2164-11-571 | 8 | d1c0535d355085ce83b703ef | 58e4a4e6d4858122ce395534 | b19fcd51bfbfbfea998617a0 |
| bio.tools | doi | 10.1038/nmeth.4106 | 8 | f00806951431db695d215baa | 97a739131d0f419542550d01 | cc0df7b86eafee0b5815fc55 |
| bio.tools | doi | 10.1093/nar/30.1.38 | 7 | ed12a2bc30ffd8cd35fb1e55 | e6cae02b0530b60896bca905 | 71a798c4a199d42be6ca270b |
| bio.tools | doi | 10.1038/npre.2011.6107 | 7 | c98a2ebc9f252a181ffd529c | 2777558e4c9b3f7c71b2f760 | 417b12301aced703a3b2cb88 |
| bio.tools | doi | 10.6084/m9.figshare.1425030.v1 | 7 | 0f34d598e4c15972b8dc5fb8 | 0de6efcc918e84f93d3de7f5 | dfc914f5a1b850d70e3a86f2 |
| bio.tools | doi | 10.1093/bioinformatics/btu146 | 6 | 13986fe3fe35dae54f9738ec | 380a142c99fa4cb31d530771 | ae77cda2f29ded8d65857c73 |
| bio.tools | doi | 10.1093/bioinformatics/btm404 | 6 | 0aea0d3707fb5cbfa66f25a5 | 728a07002a25332fd1f59b35 | d4ab794777b4c85f73c26198 |
| bio.tools | doi | 10.1007/978-3-031-76163-8_20 | 5 | c87a669b0f33c8496f2da028 | 10d8c5019659c91a004e5e11 | 3df97a68340264e2d6b40df6 |
| bio.tools | doi | 10.1109/isbi56570.2024.10635469 | 5 | aeb8968bb68e38f2404867c0 | 8b550018ae397c86c5a542f4 | 577a4ee33daa72a0944ec250 |
| bio.tools | doi | 10.48550/arxiv.2412.04094 | 5 | 056255171006ad5e494a54ca | 3662d163b675486b5caeb4fa | e684480ee6b59dbd203aff8f |
| bio.tools | doi | 10.48550/arxiv.2412.04111 | 5 | d6a998c28b12c59948c6fcb6 | da09900038b7d80952732015 | 4998ffac207bd058f9f10279 |
| bio.tools | doi | 10.1126/science.1161948 | 5 | 6e6a651a9aed8345096d48a3 | 64b8b4eb83661201c253baac | d460b2cad295fb1b3459936f |
| bio.tools | doi | 10.1093/nar/gkq1154 | 5 | 98bf7781620b197fb9dd89aa | e471731d5e1ff496e0b13092 | 0726b5951ddb91516c56121d |
| bio.tools | doi | 10.1093/nar/gkw199 | 5 | 7d0a699360a4234fa3103e9d | a0dbd91e8c57f99a7a56f43f | 9cf0f47b82502ab1b22992b1 |
| bio.tools | doi | 10.1016/j.ygeno.2017.03.001 | 5 | 12bc044f12c71913017cd4b7 | e4065862ad927e037e824c94 | 2fc47c99a8b1573248662248 |
| bio.tools | doi | 10.1093/bioinformatics/btq033 | 5 | 1c655cafde74d72c777ba66c | 6a612742e656379e1e338b93 | 1f3e044180b8670985a7c2e4 |
| bio.tools | doi | 10.1093/nar/gkx1003 | 5 | b47594ae828eb67435def3b6 | 3ac0c13c339ef91e202dabf1 | 3433e4843f76c02d36ab995e |
| bio.tools | doi | 10.1093/nar/gku1112 | 5 | 45e391322a776e951304809a | 90325dc9b89e1ee12798f0d5 | cb0c0283ce5fd1fa10c435a7 |
| bio.tools | doi | 10.1093/nar/gks1156 | 5 | 2b8404a11a98333fb4d03d17 | 1338d660c08146bb0a00ff5e | 0ca548ae4c04b62640f93b59 |
| bio.tools | doi | 10.1093/bioinformatics/btq079 | 5 | 93da7d32b7524618bb3e3312 | dfdc39b8e7107a3452b326ed | a10da20c81ad7545629cb8bf |
| bio.tools | doi | 10.1016/0888-7543(91)90071-l | 5 | 78bbb857dd9a7637d53bff53 | 316835a5ede0dae0144a74b0 | 53191c601a638af0485ba781 |
| bio.tools | doi | 10.1038/s41592-022-01488-1 | 4 | b9cb209b7e6af2c567036895 | db63a85b9a2319c421fb543e | 43e90dc38662833a654aae01 |
| bio.tools | doi | 10.3835/plantgenome2015.06.0038 | 4 | 791cd45f09871e19f697bbf6 | 40e01cdcb898b0c76913006a | 87b75f777819bb830f254b7b |
| bio.tools | doi | 10.1186/s13059-018-1491-4 | 4 | dbc1e735ae2d6349ed351fa8 | f6b0115e15ff4a9b4693b44c | 72332bce3abc24e315636ab1 |
| bio.tools | doi | 10.1093/nar/gkx1036 | 4 | 015eb2605789537e6d497106 | e76cefc4c69fcdee9678db77 | 9e2a3f1b1f03db4e0b9f8d8e |
| bio.tools | doi | 10.1186/1471-2105-11-s12-s12 | 4 | dd9fc6fd54012841a4a0e5e7 | 21e12ce43ecde719ebf2dafa | 9b81f46ed36776a4f0df6210 |
| bio.tools | doi | 10.1186/1752-0509-6-133 | 4 | 4b4c39d972e3fa982824a4ae | fc5b65d77796440ba6762c12 | bc6102d4ca010e9b092f3185 |
| bio.tools | doi | 10.1093/nar/gkr777 | 4 | e92683ff9d78b4f4b9f5d030 | 3d5332fea1d26dd55b9b4974 | ce64ef20bdbb75195803945f |
| bio.tools | doi | 10.1093/bioinformatics/btu773 | 4 | b53575e382afb7b995bf3783 | 47feb2c9f86e558f846f8e43 | 15cb2df033841d88b4b9cee9 |
| bio.tools | doi | 10.1038/nbt1160 | 4 | 3009c29e33816cba723c757e | 5efabad31f096018bd922440 | 32153565920aabb9583bc8d9 |
| bio.tools | doi | 10.1093/bioinformatics/btq293 | 4 | e0caa6a01d7b9206226fd797 | 6c7e909bb2bb2a59c2e873a4 | 6dcaf4e39ebdee038920be6d |
| bio.tools | doi | 10.1186/1758-2946-5-39 | 4 | 140172986f5d3f6d1538a561 | ff06271c751170f10780a220 | 18e09ed7cd524df19d5d6afb |
| bio.tools | doi | 10.1093/bioinformatics/bti310 | 4 | 7247fa386e5b9eb889ea35f8 | e7a7dbdc9ce6e0306bea3a96 | eede6cec30f7361400f10631 |
| bio.tools | doi | 10.1093/bioinformatics/btr330 | 4 | 907a22fa12a9d6d73baa474c | 8feff33d5ff0cecd048e5d38 | 0ffa850cb4fc286010bb85b3 |
| bio.tools | doi | 10.1155/2012/324249 | 4 | a4dbb493180f15f5033c33ee | 42a3be35540f75609f9b38c1 | d231461aecb8acbe513314a8 |
| bio.tools | doi | 10.1038/nmeth.4303 | 4 | ed164e6a94888572c66a1d19 | 22a9167eed0c1f707f76e61a | 89dad668197bf373e4ab414d |
| bio.tools | doi | 10.1007/978-1-0716-0159-4_12 | 4 | 292f861ae8db3835a1312b3d | 861354c5c80cddf7e41d3b88 | d925a567eb2ab632b3818c76 |
| bio.tools | doi | 10.1089/cmb.2012.0021 | 4 | 32c5b5fb1a6bbc3fd0a387ce | 87d05881639983d19a8457a0 | e7396cd0ee83b9d5943a3d8d |
| bio.tools | doi | 10.1186/1471-2105-10-421 | 4 | 5869ee465f536b7f28e9118b | c330da424c9f3e8f22e6d7ec | f9c96369621493074a110fcd |
| bio.tools | doi | 10.1186/1471-2105-11-573 | 4 | a95315879c709ab6ccad3536 | 0bf56bd45b2868110eda660a | 774b391db0e1db816e2c88fa |
| bio.tools | doi | 10.1371/journal.pcbi.1003118 | 4 | efce222e7c3e40c1c37db727 | d4be7b3129e623472e72dde2 | 06ce87ceb6bdb420e60e8673 |
| bio.tools | doi | 10.1038/nbt.1621 | 3 | 527b860070915a19484f7b57 | 6d40be8c8d846c70c7b6f50a | fba24764d4bc62eae03096f8 |
| bio.tools | doi | 10.1038/hortres.2016.56 | 3 | 9ac021faf56ee4b3f7a7be90 | bc63e52a7ffced45ce950eb9 | ab08852ef4c864b7d12f8fa3 |
| bio.tools | doi | 10.1093/bioinformatics/btae408 | 3 | 075f9a0569592f4ab7d2bf0c | 69f90aee2f5950a9e5b3d82a | f2b256dc8e7ee9c2f40e1aaa |
| bio.tools | doi | 10.1093/bioinformatics/bts252 | 3 | 7d3c71251dd15e2b26048ced | 3e87f9a01ab094b841617d21 | 766a6e7a33c3b42c84d285de |
| bio.tools | doi | 10.1021/acs.jcim.3c00328 | 3 | c8e634006899454cade0d2b0 | f0095bf879ba61c3603a0ff2 | 2651753ab28e3ee704deeb7a |
| bio.tools | doi | 10.1093/bioinformatics/bti325 | 3 | 5e77e84773d3bf5df481c135 | 288178bc1f5a21f519a2dd45 | e2b133cc8e86ee3b85fb7cc2 |
| bio.tools | doi | 10.1016/j.drudis.2012.05.016 | 3 | b2932fa4b7b0605d6982fb7c | 0731e03cc57ffa9ff5a463cf | 0e70a3c0b0bec0ff9fe43f23 |
| bio.tools | doi | 10.1093/nar/gkl330 | 3 | 77b26c861dd698a86447187f | 3d6a50e13e0de2cff50f7f42 | 9017cb7bded64fed324af83f |
| bio.tools | doi | 10.1093/nar/gki416 | 3 | 21f31431aaac0f9357d5fbb4 | 8ca352f90ca504d6c7391c41 | 4302d5c6e4634d78072631d6 |
| bio.tools | doi | 10.1038/nmeth.2221 | 3 | ea0bad94096d4049e039b876 | 9cc144a3c45833e16d141e14 | 52271d5dacddd4734e97ff2e |
| bio.tools | doi | 10.1093/bioinformatics/btu649 | 3 | 3565416ed1b5470ea0428319 | 64f2cbcb82a3fd86f5f93024 | 66ceb8901cfb491c548f468e |
| bio.tools | doi | 10.1002/humu.21047 | 3 | d0e8558c22991f1f663b26d9 | 86183b33af36fc969b9f1df6 | 0d981854eea7e2af34159761 |
| bio.tools | doi | 10.1093/nar/gkn730 | 3 | 2981307a2dd03707f0346f52 | 0fe7aa0f7ab5a22f8fb66c0b | a1f3e8d13d407cfb4df93fae |
| bio.tools | doi | 10.1186/s13059-016-0974-4 | 3 | 5227a7a7e92e0507e70e9122 | 4ffc017c67a170ecccc43c44 | fb1b0e5f870f21c32a8c813d |

# parquet_files/train/train_applprev_1_0.parquet

- Run ID: 20260224T161905Z_b668328e

- Linhas: 3887684

- Colunas: 41


## Colunas

| column | dtype | null_pct | approx_nunique | examples |
|---|---|---:|---:|---|
| actualdpd_943P | double | 0.06 | 101 | 102.0, 1.0, 116.0, 233.0, 22.0 |
| annuity_853A | double | 4.01 | 76227 | 5297.6, 2566.8, 6687.2, 2001.4, 2066.2 |
| approvaldate_319D | string | 45.43 | 5131 | 2019-08-08, 2019-08-22, 2017-05-14, 2013-03-14, 2017-12-05 |
| byoccupationinc_3656910L | double | 74.49 | 25077 | 45568.0, 25921.0, 29625.0, 12985.0, 58859.0 |
| cancelreason_3545846M | string | 0.0 | 66 | P205_40_167, P150_0_30, P60_137_164, P166_126_174, P98_38_170 |
| case_id | bigint | 0.0 | 769925 | 296, 467, 1159, 2136, 2162 |
| childnum_21L | double | 50.26 | 20 | 1.0, 20.0, 15.0, 0.0, 9.0 |
| creationdate_885D | string | 0.0 | 5131 | 2016-08-17, 2015-05-01, 2017-12-05, 2006-09-24, 2014-05-27 |
| credacc_actualbalance_314A | double | 95.67 | 60707 | 0.216, 102.0, 20294.0, 0.89799994, 30196.0 |
| credacc_credlmt_575A | double | 3.06 | 36832 | 48996.0, 41006.0, 26224.0, 18434.0, 58284.6 |
| credacc_maxhisbal_375A | double | 95.67 | 42649 | -17474.053, 102.0, -38612.51, -4819.368, -9534.0 |
| credacc_minhisbal_90A | double | 95.67 | 41098 | -62812.758, 102.0, -19029.898, -23505.215, -4819.368 |
| credacc_status_367L | string | 95.67 | 6 | PCL, CL, CA, PO, CR |
| credacc_transactions_402L | double | 95.67 | 82 | 1.0, 50.0, 22.0, 38.0, 66.0 |
| credamount_590A | double | 3.17 | 193000 | 8982.0, 38400.0, 48996.0, 61976.0, 22600.0 |
| credtype_587L | string | 3.17 | 3 | REL, CAL, COL |
| currdebt_94A | double | 32.68 | 349538 | 36232.0, 27507.498, 29994.604, 67566.52, 36676.26 |
| dateactivated_425D | string | 47.45 | 4012 | 2019-08-08, 2019-08-23, 2019-08-22, 2008-12-03, 2017-12-05 |
| district_544M | string | 0.0 | 481 | P87_135_164, P181_5_55, P59_58_91, P108_34_171, P175_64_60 |
| downpmt_134A | double | 3.17 | 18035 | 1008.0, 22600.0, 3787.8, 3978.4001, 959.4 |
| dtlastpmt_581D | string | 73.58 | 2112 | 2019-08-08, 2019-08-22, 2019-08-23, 2017-12-05, 2015-05-01 |
| dtlastpmtallstes_3545839D | string | 62.61 | 2133 | 2019-08-08, 2019-08-22, 2019-08-23, 2017-12-05, 2015-05-01 |
| education_1138M | string | 0.0 | 6 | P97_36_170, P33_146_175, P157_18_172, P17_36_170, a55475b1 |
| employedfrom_700D | string | 56.1 | 9345 | 2010-09-24, 1979-05-15, 2009-06-23, 2014-02-22, 2016-08-17 |
| familystate_726L | string | 32.03 | 5 | WIDOWED, SINGLE, MARRIED, LIVING_WITH_PARTNER, DIVORCED |
| firstnonzeroinstldate_307D | string | 9.39 | 4973 | 2007-04-29, 2017-12-05, 2015-05-01, 2014-05-27, 2007-09-13 |
| inittransactioncode_279L | string | 3.17 | 3 | CASH, POS, NDF |
| isbidproduct_390L | boolean | 0.0 | 2 | false, true |
| isdebitcard_527L | boolean | 93.57 | 2 | false, true |
| mainoccupationinc_437A | double | 0.94 | 21455 | 11680.0, 22600.0, 38400.0, 5883.2, 49400.0 |
| maxdpdtolerance_577P | double | 46.75 | 3016 | 102.0, 1008.0, 247.0, 373.0, 151.0 |
| num_group1 | bigint | 0.0 | 20 | 7, 15, 11, 3, 8 |
| outstandingdebt_522A | double | 32.87 | 253721 | 36232.0, 115021.805, 161623.8, 1950.4, 11721.4 |
| pmtnum_8L | double | 8.05 | 54 | 50.0, 22.0, 38.0, 20.0, 15.0 |
| postype_4733339M | string | 0.0 | 9 | P46_145_78, P169_115_83, P177_117_192, P217_110_186, P149_40_170 |
| profession_152M | string | 0.0 | 9077 | P135_113_37, P133_97_187, P91_94_116, P49_3_144, P201_139_11 |
| rejectreason_755M | string | 0.0 | 18 | P48_22_32, P30_86_84, P5_143_178, P84_14_61, P94_109_143 |
| rejectreasonclient_4145042M | string | 0.0 | 11 | P30_86_84, P5_143_178, P84_14_61, P94_109_143, P69_72_116 |
| revolvingaccount_394A | double | 95.97 | 62668 | 7.801153E8, 7.8029946E8, 7.8077485E8, 7.41382E8, 7.600987E8 |
| status_219L | string | 0.0 | 11 | K, Q, T, L, D |
| tenor_203L | double | 8.05 | 54 | 50.0, 22.0, 38.0, 20.0, 15.0 |

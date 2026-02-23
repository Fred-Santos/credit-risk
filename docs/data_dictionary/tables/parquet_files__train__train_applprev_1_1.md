# parquet_files/train/train_applprev_1_1.parquet

- Run ID: 20260223T175139Z_1bc1491e

- Linhas: 2638295

- Colunas: 41


## Colunas

| column | dtype | null_pct | approx_nunique | examples |
|---|---|---:|---:|---|
| actualdpd_943P | double | 0.01 | 149 | 151.0, 102.0, 1.0, 251.0, 1943.0 |
| annuity_853A | double | 3.6 | 73609 | 1496.0, 2494.2, 2402.2, 3120.8, 1405.8 |
| approvaldate_319D | string | 47.16 | 5468 | 2019-08-08, 2019-08-22, 2020-02-26, 2020-04-13, 2016-08-17 |
| byoccupationinc_3656910L | double | 79.43 | 18546 | 59120.0, 29625.0, 62155.0, 25921.0, 12985.0 |
| cancelreason_3545846M | string | 0.0 | 70 | P205_40_167, P150_0_30, P60_137_164, P166_126_174, P98_38_170 |
| case_id | bigint | 0.0 | 434460 | 41785, 42686, 42743, 44423, 44446 |
| childnum_21L | double | 60.85 | 19 | 1.0, 20.0, 15.0, 0.0, 9.0 |
| creationdate_885D | string | 0.0 | 5468 | 2019-08-08, 2015-05-01, 2014-02-16, 2017-12-05, 2019-08-23 |
| credacc_actualbalance_314A | double | 94.24 | 46502 | 31916.4, 1008.0, 102.0, 162.21, 13.816001 |
| credacc_credlmt_575A | double | 2.85 | 28753 | 142484.0, 31916.4, 48996.0, 79980.0, 19768.0 |
| credacc_maxhisbal_375A | double | 94.24 | 37322 | 102.0, 1568.2001, 162.21, -59209.883, -10173.938 |
| credacc_minhisbal_90A | double | 94.24 | 38940 | 102.0, 13.816001, 167.136, 3.148, -26516.8 |
| credacc_status_367L | string | 94.24 | 6 | PCL, CL, CA, PO, CR |
| credacc_transactions_402L | double | 94.24 | 88 | 1.0, 50.0, 22.0, 65.0, 38.0 |
| credamount_590A | double | 2.99 | 168773 | 43227.0, 48996.0, 37996.402, 21592.0, 30196.0 |
| credtype_587L | string | 2.99 | 3 | REL, CAL, COL |
| currdebt_94A | double | 37.0 | 203776 | 9880.856, 11644.971, 66708.445, 26368.834, 13604.4 |
| dateactivated_425D | string | 49.16 | 4282 | 2020-02-26, 2019-08-23, 2019-08-08, 2019-08-22, 2017-12-05 |
| district_544M | string | 0.0 | 1049 | P87_135_164, P181_5_55, P83_38_175, P133_68_68, P80_66_131 |
| downpmt_134A | double | 2.99 | 13278 | 1436.0, 1336.0, 7950.0, 2148.8, 5274.0 |
| dtlastpmt_581D | string | 71.64 | 2305 | 2020-02-26, 2019-08-23, 2019-08-22, 2019-08-08, 2016-08-17 |
| dtlastpmtallstes_3545839D | string | 61.0 | 2330 | 2020-02-26, 2019-08-23, 2019-08-22, 2019-08-08, 2016-08-17 |
| education_1138M | string | 0.0 | 6 | P97_36_170, P33_146_175, P157_18_172, P17_36_170, a55475b1 |
| employedfrom_700D | string | 64.65 | 8426 | 2016-08-17, 2014-02-16, 2019-08-22, 1986-09-03, 1990-03-24 |
| familystate_726L | string | 43.54 | 5 | WIDOWED, SINGLE, MARRIED, LIVING_WITH_PARTNER, DIVORCED |
| firstnonzeroinstldate_307D | string | 10.89 | 5244 | 2019-08-08, 2019-08-22, 2019-08-23, 2013-03-14, 2010-02-12 |
| inittransactioncode_279L | string | 2.99 | 3 | CASH, POS, NDF |
| isbidproduct_390L | boolean | 0.0 | 2 | false, true |
| isdebitcard_527L | boolean | 91.93 | 2 | false, true |
| mainoccupationinc_437A | double | 2.48 | 17751 | 22600.0, 38400.0, 73200.0, 59120.0, 195800.0 |
| maxdpdtolerance_577P | double | 48.45 | 2932 | 247.0, 1495.0, 151.0, 102.0, 602.0 |
| num_group1 | bigint | 0.0 | 20 | 7, 15, 11, 3, 8 |
| outstandingdebt_522A | double | 37.16 | 186655 | 9880.856, 11644.971, 13604.4, 202550.4, 12009.8 |
| pmtnum_8L | double | 9.06 | 57 | 50.0, 22.0, 38.0, 20.0, 15.0 |
| postype_4733339M | string | 0.0 | 9 | P46_145_78, P169_115_83, P177_117_192, P217_110_186, P149_40_170 |
| profession_152M | string | 0.0 | 5672 | P135_113_37, P121_92_147, P31_119_149, P105_95_53, P49_3_144 |
| rejectreason_755M | string | 0.0 | 18 | P48_22_32, P30_86_84, P5_143_178, P84_14_61, P94_109_143 |
| rejectreasonclient_4145042M | string | 0.0 | 14 | P59_114_135, P30_86_84, P5_143_178, P84_14_61, P94_109_143 |
| revolvingaccount_394A | double | 94.69 | 53431 | 7.807986E8, 8.001941E8, 8.0023744E8, 8.0033274E8, 8.0060634E8 |
| status_219L | string | 0.0 | 11 | K, Q, T, L, D |
| tenor_203L | double | 9.06 | 57 | 50.0, 22.0, 38.0, 20.0, 15.0 |

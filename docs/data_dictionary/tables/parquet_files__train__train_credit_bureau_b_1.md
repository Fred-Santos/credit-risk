# parquet_files/train/train_credit_bureau_b_1.parquet

- Run ID: 20260223T175139Z_1bc1491e

- Linhas: 85791

- Colunas: 45


## Colunas

| column | dtype | null_pct | approx_nunique | examples |
|---|---|---:|---:|---|
| amount_1115A | double | 49.08 | 20454 | 194000.0, 321024.0, 77196.0, 13498.2, 22600.0 |
| case_id | bigint | 0.0 | 38099 | 467, 33665, 33783, 38252, 38271 |
| classificationofcontr_1114M | string | 0.0 | 9 | ea6782cc, 436d55c2, 1cf4e481, 90c587b1, 00135d9c |
| contractdate_551D | string | 4.54 | 4087 | 2017-05-14, 2017-12-05, 2019-08-23, 2019-08-22, 2013-03-14 |
| contractmaturitydate_151D | string | 4.75 | 4515 | 2019-08-08, 2019-08-23, 2020-02-26, 2019-08-22, 2024-08-20 |
| contractst_516M | string | 0.0 | 15 | 83931972, dd67cff0, 54132f86, 04bf6e27, 7640edc3 |
| contracttype_653M | string | 0.0 | 26 | 1c9c5356, f4e17141, 60e784d6, 190917cc, 920c2ccd |
| credlmt_1052A | double | 67.85 | 9811 | 194000.0, 116771.2, 22600.0, 52156.0, 294554.0 |
| credlmt_228A | double | 81.2 | 3523 | 22600.0, 74600.0, 49982.2, 38400.0, 73200.0 |
| credlmt_3940954A | double | 55.45 | 9656 | 46938.0, 22600.0, 194000.0, 116771.2, 132421.0 |
| credor_3940957M | string | 0.0 | 154 | a294b063, a2979b07, 74bd67a8, 5ce9749d, d6eab789 |
| credquantity_1099L | double | 38.2 | 14 | 1.0, 9.0, 12.0, 10.0, 5.0 |
| credquantity_984L | double | 46.12 | 70 | 1.0, 50.0, 22.0, 38.0, 66.0 |
| debtpastduevalue_732A | double | 5.33 | 5770 | 3993.912, 96237.44, 2558.212, 180680.16, 36230.0 |
| debtvalue_227A | double | 49.08 | 40290 | 69718.39, 34776.26, 38110.836, 182918.84, 98884.4 |
| dpd_550P | double | 38.2 | 4861 | 20909.0, 26100.0, 183420.0, 251999.0, 99927.0 |
| dpd_733P | double | 46.12 | 42 | 1.0, 67934.0, 90000.0, 38.0, 20.0 |
| dpdmax_851P | double | 5.32 | 19744 | 192955.0, 20909.0, 31301.0, 4174.0, 9984.0 |
| dpdmaxdatemonth_804T | double | 5.32 | 12 | 1.0, 9.0, 12.0, 10.0, 5.0 |
| dpdmaxdateyear_742T | double | 5.32 | 15 | 2013.0, 2019.0, 1900.0, 2018.0, 2014.0 |
| installmentamount_644A | double | 46.12 | 85 | 1.0, 1.8000001, 3009.0, 14947.2, 4183.2 |
| installmentamount_833A | double | 38.2 | 39701 | 69718.39, 34776.26, 47856.047, 37097.062, 182918.84 |
| instlamount_892A | double | 49.3 | 32457 | 2566.8, 10251.2, 1161.2001, 10286.132, 12279.492 |
| interesteffectiverate_369L | double | 88.92 | 2752 | 52.73, 34.71, 40.67, 31.47, 48.04 |
| interestrateyearly_538L | double | 66.4 | 390 | 8.5, 10.7, 1.0, 20.5, 48.37 |
| lastupdate_260D | string | 4.54 | 632 | 2019-08-08, 2020-02-26, 2020-04-13, 2019-08-22, 2019-04-25 |
| maxdebtpduevalodued_3940955A | double | 5.32 | 1428 | 91.8, 119.8, 102.0, 151.0, 1.0 |
| num_group1 | bigint | 0.0 | 21 | 7, 15, 11, 3, 8 |
| numberofinstls_810L | double | 49.3 | 239 | 102.0, 151.0, 247.0, 1.0, 84.0 |
| overdueamountmax_950A | double | 5.32 | 1788 | 119.8, 194.40001, 102.0, 91.8, 429.6 |
| overdueamountmaxdatemonth_494T | double | 5.32 | 12 | 1.0, 9.0, 12.0, 10.0, 5.0 |
| overdueamountmaxdateyear_432T | double | 5.32 | 15 | 2013.0, 2019.0, 1900.0, 2018.0, 2014.0 |
| periodicityofpmts_997L | string | 97.64 | 5 | Ежеквартальные платежи - 90 дней, В день истечения срока кредитного договора, Ежемесячные платежи - 30 дней, Полугодовые платежи - 180 дней, Взносы с нерегулярной периодичностью |
| periodicityofpmts_997M | string | 3.81 | 9 | 842dca9f, 0a59e5b4, e4c51201, d479a207, e24bdef1 |
| pmtdaysoverdue_1135P | double | 5.33 | 1582 | 1436.0, 1974.0, 151.0, 102.0, 247.0 |
| pmtmethod_731M | string | 0.0 | 10 | f6e26148, dbcbe8f8, daad4854, 10984579, 5f8f7038 |
| pmtnumpending_403L | double | 49.09 | 255 | 151.0, 102.0, 1.0, 84.0, 116.0 |
| purposeofcred_722M | string | 0.0 | 16 | 5065c2b8, 6ec903ee, 60c73645, b1285059, e8f3b178 |
| residualamount_1093A | double | 81.2 | 2 | 0.0, 322.0 |
| residualamount_127A | double | 67.85 | 17182 | 47856.047, 37097.062, 186474.48, 23404.6, 230913.23 |
| residualamount_3940956A | double | 56.27 | 23058 | 111684.04, 47856.047, 142879.8, 37097.062, 23404.6 |
| subjectrole_326M | string | 0.0 | 6 | ab3c25cf, 15f04f45, P28_48_88, fa4f56f1, daf49a8a |
| subjectrole_43M | string | 0.0 | 6 | ab3c25cf, 15f04f45, fa4f56f1, daf49a8a, a55475b1 |
| totalamount_503A | double | 38.2 | 25087 | 194000.0, 22600.0, 286491.16, 116771.2, 128740.6 |
| totalamount_881A | double | 46.12 | 28853 | 194000.0, 22600.0, 367327.4, 88117.805, 11572.601 |

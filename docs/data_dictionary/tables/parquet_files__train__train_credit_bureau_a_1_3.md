# parquet_files/train/train_credit_bureau_a_1_3.parquet

- Run ID: 20260223T175139Z_1bc1491e

- Linhas: 2079323

- Colunas: 79


## Colunas

| column | dtype | null_pct | approx_nunique | examples |
|---|---|---:|---:|---|
| annualeffectiverate_199L | double | 92.31 | 5349 | 10.7, 40.67, 48.04, 28.37, 34.71 |
| annualeffectiverate_63L | double | 98.17 | 4539 | 34.71, 42.87, 48.04, 28.79, 26.63 |
| case_id | bigint | 0.0 | 185189 | 52206, 52800, 52991, 53380, 53616 |
| classificationofcontr_13M | string | 0.0 | 9 | be7b251d, ea6782cc, 1cf4e481, 2c070815, 00135d9c |
| classificationofcontr_400M | string | 0.0 | 302 | 51590aa9, acba4f13, fa2a66b3, 01938327, e6e56e83 |
| contractst_545M | string | 0.0 | 28 | 83931972, dd67cff0, 54132f86, 64e60bdd, 7640edc3 |
| contractst_964M | string | 0.0 | 231 | cae5106c, 690c65e6, 7d6eb162, 2efab1d0, fb43439d |
| contractsum_5085717L | double | 85.3 | 223100 | 45667.05, 110055.56, 424280.25, 43227.0, 260726.51 |
| credlmt_230A | double | 92.66 | 13921 | 74600.0, 124267.6, 22600.0, 49400.0, 38400.0 |
| credlmt_935A | double | 92.58 | 27028 | 125978.0, 194000.0, 502908.0, 30576.0, 359814.0 |
| dateofcredend_289D | string | 84.21 | 5829 | 2021-11-03, 2019-08-22, 2024-08-20, 2023-05-01, 2022-10-05 |
| dateofcredend_353D | string | 39.08 | 9159 | 2020-02-26, 2008-11-19, 2020-04-13, 2019-08-22, 2016-08-17 |
| dateofcredstart_181D | string | 39.08 | 6214 | 2019-08-22, 2016-08-17, 2008-11-19, 2020-02-26, 2019-08-08 |
| dateofcredstart_739D | string | 84.21 | 4512 | 2010-02-12, 2019-08-08, 2019-08-22, 2020-02-26, 2017-05-14 |
| dateofrealrepmt_138D | string | 39.37 | 5840 | 2007-03-06, 2020-02-26, 2013-03-14, 2008-11-19, 2019-08-22 |
| debtoutstand_525A | double | 91.5 | 131872 | 88467.65, 146527.88, 63818.082, 94218.16, 46777.203 |
| debtoverdue_47A | double | 91.5 | 2408 | 113.54201, 91.8, 63067.85, 75234.0, 426.62204 |
| description_351M | string | 0.0 | 12 | 0cb4d552, 95decc86, 153cfa61, 0bfbf8f5, 8a7423d5 |
| dpdmax_139P | double | 84.3 | 1115 | 151.0, 247.0, 102.0, 1336.0, 1.0 |
| dpdmax_757P | double | 41.01 | 3420 | 247.0, 373.0, 886.0, 1047.0, 151.0 |
| dpdmaxdatemonth_442T | double | 41.01 | 12 | 1.0, 9.0, 12.0, 10.0, 5.0 |
| dpdmaxdatemonth_89T | double | 84.3 | 12 | 1.0, 9.0, 12.0, 10.0, 5.0 |
| dpdmaxdateyear_596T | double | 84.3 | 5 | 2019.0, 2018.0, 2017.0, 2016.0, 2020.0 |
| dpdmaxdateyear_896T | double | 41.01 | 18 | 2013.0, 2019.0, 2006.0, 2018.0, 2004.0 |
| financialinstitution_382M | string | 0.0 | 244 | 7645b0cf, f43b5c1d, f0606fbf, 19f06752, 10340b4b |
| financialinstitution_591M | string | 0.0 | 150 | 327249ff, f0606fbf, eb77f8bf, 2eb16123, ec92ab0d |
| instlamount_768A | double | 92.67 | 50465 | 3494.2239, 3879.6, 829.4, 4588.8003, 5769.6 |
| instlamount_852A | double | 95.08 | 23106 | 3354.0, 5297.6, 1812.6, 1974.0, 1.424 |
| interestrate_508L | double | 99.5 | 139 | 8.5, 18.96, 20.5, 26.5, 14.2 |
| lastupdate_1112D | string | 84.21 | 207 | 2020-06-24, 2020-06-08, 2020-09-12, 2020-06-20, 2020-06-22 |
| lastupdate_388D | string | 39.09 | 4891 | 2014-12-13, 2016-08-17, 2019-08-22, 2020-02-26, 2011-01-29 |
| monthlyinstlamount_332A | double | 84.31 | 111455 | 3494.2239, 10286.132, 12279.492, 3879.6, 6138.662 |
| monthlyinstlamount_674A | double | 42.71 | 282533 | 1256.5901, 4864.0, 1047.0, 6174.2, 4850.8003 |
| nominalrate_281L | double | 93.94 | 556 | 8.5, 10.7, 28.37, 20.5, 38.3 |
| nominalrate_498L | double | 76.78 | 1507 | 8.5, 43.67, 78.9, 1336.0, 38.3 |
| num_group1 | bigint | 0.0 | 198 | 125, 7, 51, 124, 169 |
| numberofcontrsvalue_258L | double | 92.39 | 18 | 1.0, 0.0, 9.0, 10.0, 5.0 |
| numberofcontrsvalue_358L | double | 91.63 | 113 | 1.0, 84.0, 50.0, 75.0, 22.0 |
| numberofinstls_229L | double | 46.44 | 320 | 102.0, 151.0, 247.0, 1.0, 360.0 |
| numberofinstls_320L | double | 91.63 | 279 | 151.0, 102.0, 247.0, 1.0, 302.0 |
| numberofoutstandinstls_520L | double | 46.41 | 170 | 102.0, 1.0, 302.0, 116.0, 466.0 |
| numberofoutstandinstls_59L | double | 91.63 | 282 | 102.0, 151.0, 247.0, 1.0, 84.0 |
| numberofoverdueinstlmax_1039L | double | 84.21 | 1245 | 151.0, 102.0, 373.0, 247.0, 1436.0 |
| numberofoverdueinstlmax_1151L | double | 39.08 | 3683 | 1405.0, 151.0, 102.0, 1436.0, 1047.0 |
| numberofoverdueinstlmaxdat_148D | string | 81.83 | 4837 | 2020-02-26, 2011-01-29, 2017-12-05, 2019-08-22, 2019-08-08 |
| numberofoverdueinstlmaxdat_641D | string | 95.73 | 1685 | 2020-02-26, 2019-08-22, 2017-12-05, 2019-08-08, 2020-04-13 |
| numberofoverdueinstls_725L | double | 84.3 | 571 | 247.0, 1.0, 302.0, 685.0, 1057.0 |
| numberofoverdueinstls_834L | double | 39.16 | 111 | 1.0, 251.0, 310.0, 20.0, 15.0 |
| outstandingamount_354A | double | 46.39 | 149 | 9760.0, 1.0, 8.2, 1.8000001, 4356.0 |
| outstandingamount_362A | double | 91.63 | 158765 | 146527.88, 22260.793, 94218.16, 27308.932, 23374.559 |
| overdueamount_31A | double | 39.15 | 180 | 147673.92, 1.0, 8.2, 1.8000001, 214525.0 |
| overdueamount_659A | double | 84.3 | 2747 | 113.54201, 91.8, 75234.0, 3898.072, 426.62204 |
| overdueamountmax2_14A | double | 84.21 | 77310 | 11484.69, 4075.17, 4844.0264, 1304.6, 7588.394 |
| overdueamountmax2_398A | double | 39.08 | 229033 | 1336.0, 4712.7144, 28.218, 2820.8, 1496.0 |
| overdueamountmax2date_1002D | string | 82.01 | 4615 | 2009-01-04, 2011-01-29, 2017-12-05, 2020-02-26, 2019-08-08 |
| overdueamountmax2date_1142D | string | 95.7 | 1763 | 2020-02-26, 2019-08-22, 2017-12-05, 2019-08-08, 2020-04-13 |
| overdueamountmax_155A | double | 84.21 | 58801 | 4075.17, 4844.0264, 1304.6, 5545.388, 32831.242 |
| overdueamountmax_35A | double | 40.94 | 202839 | 1336.0, 4712.7144, 28.218, 2820.8, 1496.0 |
| overdueamountmaxdatemonth_284T | double | 40.94 | 12 | 1.0, 9.0, 12.0, 10.0, 5.0 |
| overdueamountmaxdatemonth_365T | double | 84.21 | 12 | 1.0, 9.0, 12.0, 10.0, 5.0 |
| overdueamountmaxdateyear_2T | double | 84.21 | 5 | 2019.0, 2018.0, 2017.0, 2016.0, 2020.0 |
| overdueamountmaxdateyear_994T | double | 40.94 | 18 | 2013.0, 2019.0, 2006.0, 2018.0, 2004.0 |
| periodicityofpmts_1102L | double | 52.39 | 5 | 1.0, 360.0, 90.0, 180.0, 30.0 |
| periodicityofpmts_837L | double | 91.8 | 5 | 1.0, 360.0, 90.0, 180.0, 30.0 |
| prolongationcount_1120L | double | 95.11 | 52 | 1.0, 22.0, 20.0, 15.0, 67.0 |
| prolongationcount_599L | double | 99.47 | 27 | 1.0, 22.0, 15.0, 17.0, 0.0 |
| purposeofcred_426M | string | 0.0 | 17 | 6ec903ee, 60c73645, b1285059, e8f3b178, 5d1b0cdd |
| purposeofcred_874M | string | 0.0 | 25 | 5065c2b8, 6ec903ee, 60c73645, b1285059, e8f3b178 |
| refreshdate_3813885D | string | 32.05 | 128 | 2020-06-24, 2020-09-12, 2020-06-22, 2020-06-20, 2020-07-25 |
| residualamount_488A | double | 92.74 | 1 | 0.0 |
| residualamount_856A | double | 92.67 | 78044 | 87048.54, 88467.65, 3447.6, 63818.082, 82984.77 |
| subjectrole_182M | string | 0.0 | 6 | ab3c25cf, 15f04f45, P28_48_88, be4fd70b, daf49a8a |
| subjectrole_93M | string | 0.0 | 8 | ab3c25cf, 15f04f45, 0c42a10e, be4fd70b, daf49a8a |
| totalamount_6A | double | 46.38 | 196090 | 194000.0, 17283.201, 30196.0, 27038.0, 38400.0 |
| totalamount_996A | double | 91.63 | 59983 | 36726.402, 194000.0, 129845.2, 83248.4, 963515.6 |
| totaldebtoverduevalue_178A | double | 92.39 | 2422 | 113.54201, 91.8, 63067.85, 75234.0, 426.62204 |
| totaldebtoverduevalue_718A | double | 91.63 | 179 | 147673.92, 1.0, 8.2, 1.8000001, 214525.0 |
| totaloutstanddebtvalue_39A | double | 92.39 | 133530 | 88467.65, 146527.88, 63818.082, 94218.16, 46777.203 |
| totaloutstanddebtvalue_668A | double | 91.63 | 139 | 9760.0, 1.0, 8.2, 1.8000001, 4356.0 |

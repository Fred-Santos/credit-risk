# parquet_files/train/train_credit_bureau_a_1_2.parquet

- Run ID: 20260223T175139Z_1bc1491e

- Linhas: 3743810

- Colunas: 79


## Colunas

| column | dtype | null_pct | approx_nunique | examples |
|---|---|---:|---:|---|
| annualeffectiverate_199L | double | 93.26 | 5621 | 52.73, 34.63, 40.67, 23.97, 48.04 |
| annualeffectiverate_63L | double | 97.74 | 4568 | 17.42, 48.04, 20.64, 55.41, 40.67 |
| case_id | bigint | 0.0 | 325856 | 41105, 41157, 41785, 41998, 42370 |
| classificationofcontr_13M | string | 0.0 | 10 | be7b251d, ea6782cc, 1cf4e481, 2c070815, 00135d9c |
| classificationofcontr_400M | string | 0.0 | 343 | 51590aa9, acba4f13, ffee884a, fa2a66b3, 01938327 |
| contractst_545M | string | 0.0 | 38 | 83931972, dd67cff0, 54132f86, 7640edc3, 823dcc3b |
| contractst_964M | string | 0.0 | 241 | cae5106c, 690c65e6, 7d6eb162, fba26f92, fb43439d |
| contractsum_5085717L | double | 99.63 | 10739 | 50355.0, 1182216.52, 8.5, 54893.74, 27809.67 |
| credlmt_230A | double | 92.83 | 18942 | 41088.8, 33508.402, 22600.0, 46110.402, 13768.4 |
| credlmt_935A | double | 91.81 | 50137 | 175233.2, 65494.0, 17201.8, 46298.0, 464563.22 |
| dateofcredend_289D | string | 82.55 | 7939 | 2020-04-13, 2024-07-14, 2022-10-05, 2020-02-26, 2023-05-18 |
| dateofcredend_353D | string | 44.61 | 9751 | 2014-05-27, 2011-01-29, 2019-08-22, 2017-12-05, 2019-08-08 |
| dateofcredstart_181D | string | 44.61 | 6232 | 2019-08-22, 2008-11-19, 2014-02-16, 2016-08-17, 2019-08-23 |
| dateofcredstart_739D | string | 82.55 | 4807 | 2019-08-22, 2017-12-05, 2019-08-08, 2019-08-23, 2014-05-27 |
| dateofrealrepmt_138D | string | 44.91 | 5872 | 2015-05-01, 2019-08-22, 2019-08-23, 2007-03-06, 2009-12-04 |
| debtoutstand_525A | double | 91.31 | 273434 | 584760.56, 557045.1, 280390.34, 1.5041912E7, 433908.25 |
| debtoverdue_47A | double | 91.31 | 13558 | 10600.766, 4856.0, 1159.848, 75234.0, 566.838 |
| description_351M | string | 0.0 | 12 | 0cb4d552, 95decc86, 153cfa61, 0bfbf8f5, 8a7423d5 |
| dpdmax_139P | double | 82.67 | 2273 | 1336.0, 1974.0, 151.0, 102.0, 1763.0 |
| dpdmax_757P | double | 46.45 | 3668 | 102.0, 151.0, 373.0, 247.0, 602.0 |
| dpdmaxdatemonth_442T | double | 46.45 | 12 | 1.0, 9.0, 12.0, 10.0, 5.0 |
| dpdmaxdatemonth_89T | double | 82.67 | 12 | 1.0, 9.0, 12.0, 10.0, 5.0 |
| dpdmaxdateyear_596T | double | 82.67 | 5 | 2019.0, 2018.0, 2017.0, 2016.0, 2020.0 |
| dpdmaxdateyear_896T | double | 46.45 | 19 | 2013.0, 2019.0, 2006.0, 2018.0, 2004.0 |
| financialinstitution_382M | string | 0.0 | 318 | c0edbb2e, f0606fbf, f43b5c1d, eb77f8bf, 2eb16123 |
| financialinstitution_591M | string | 0.0 | 179 | 327249ff, f0606fbf, 19f06752, 2eb16123, ec92ab0d |
| instlamount_768A | double | 91.93 | 81259 | 4588.8003, 3120.8, 1568.2001, 1405.8, 2765.8 |
| instlamount_852A | double | 95.17 | 34749 | 3131.678, 647.96405, 5613.138, 5046.786, 1198.892 |
| interestrate_508L | double | 99.48 | 196 | 8.5, 12535.0, 20.5, 18.96, 26.5 |
| lastupdate_1112D | string | 82.55 | 293 | 2020-02-26, 2020-04-13, 2020-06-08, 2020-01-05, 2020-04-12 |
| lastupdate_388D | string | 44.61 | 4878 | 2011-01-29, 2019-08-23, 2017-12-05, 2019-08-08, 2019-08-22 |
| monthlyinstlamount_332A | double | 82.68 | 187890 | 4588.8003, 6222.368, 3120.8, 1568.2001, 4729.022 |
| monthlyinstlamount_674A | double | 48.17 | 351815 | 3131.678, 1974.0, 2013.85, 2457.6, 7950.0 |
| nominalrate_281L | double | 93.44 | 821 | 8.5, 38.3, 1.0, 884.0, 20.5 |
| nominalrate_498L | double | 80.51 | 1687 | 8.5, 43.67, 78.9, 10.7, 38.3 |
| num_group1 | bigint | 0.0 | 518 | 296, 467, 125, 451, 7 |
| numberofcontrsvalue_258L | double | 91.92 | 25 | 1.0, 20.0, 15.0, 17.0, 0.0 |
| numberofcontrsvalue_358L | double | 91.8 | 128 | 102.0, 1.0, 84.0, 50.0, 75.0 |
| numberofinstls_229L | double | 51.81 | 361 | 247.0, 102.0, 151.0, 1.0, 360.0 |
| numberofinstls_320L | double | 90.74 | 313 | 151.0, 102.0, 1.0, 302.0, 84.0 |
| numberofoutstandinstls_520L | double | 51.77 | 210 | 102.0, 1.0, 360.0, 84.0, 310.0 |
| numberofoutstandinstls_59L | double | 90.74 | 293 | 102.0, 151.0, 1.0, 84.0, 116.0 |
| numberofoverdueinstlmax_1039L | double | 82.55 | 2321 | 151.0, 102.0, 373.0, 4174.0, 1047.0 |
| numberofoverdueinstlmax_1151L | double | 44.61 | 3837 | 151.0, 1495.0, 602.0, 102.0, 886.0 |
| numberofoverdueinstlmaxdat_148D | string | 83.54 | 4784 | 2017-05-14, 2019-08-22, 2019-08-08, 2011-01-29, 2017-12-05 |
| numberofoverdueinstlmaxdat_641D | string | 95.57 | 2125 | 2019-08-22, 2019-08-08, 2019-08-23, 2017-12-05, 2020-02-26 |
| numberofoverdueinstls_725L | double | 82.67 | 2005 | 151.0, 102.0, 4174.0, 1047.0, 247.0 |
| numberofoverdueinstls_834L | double | 44.69 | 180 | 247.0, 1.0, 459.0, 472.0, 251.0 |
| outstandingamount_354A | double | 51.75 | 311 | 6350.0, 4856.0, 1.0, 8.2, 1.8000001 |
| outstandingamount_362A | double | 90.74 | 325192 | 141063.48, 2641.72, 128174.19, 148799.0, 66792.65 |
| overdueamount_31A | double | 44.67 | 311 | 82577.0, 1.0, 8.2, 106925.0, 1.8000001 |
| overdueamount_659A | double | 82.67 | 15492 | 10600.766, 75234.0, 6240.8003, 30084.0, 8285.2 |
| overdueamountmax2_14A | double | 82.55 | 127432 | 2797.17, 2218.81, 8165.236, 1246.3041, 58206.457 |
| overdueamountmax2_398A | double | 44.61 | 326340 | 6540.93, 5.1580005, 55330.875, 247.0, 8274.536 |
| overdueamountmax2date_1002D | string | 83.68 | 4680 | 2011-01-29, 2009-01-04, 2019-08-22, 2017-12-05, 2015-05-01 |
| overdueamountmax2date_1142D | string | 95.53 | 2124 | 2019-08-08, 2019-08-22, 2017-12-05, 2019-08-23, 2020-02-26 |
| overdueamountmax_155A | double | 82.55 | 97694 | 3292.052, 2218.81, 1246.3041, 58206.457, 27345.191 |
| overdueamountmax_35A | double | 46.38 | 319217 | 6540.93, 5.1580005, 247.0, 8274.536, 7987.0 |
| overdueamountmaxdatemonth_284T | double | 46.38 | 12 | 1.0, 9.0, 12.0, 10.0, 5.0 |
| overdueamountmaxdatemonth_365T | double | 82.55 | 12 | 1.0, 9.0, 12.0, 10.0, 5.0 |
| overdueamountmaxdateyear_2T | double | 82.55 | 5 | 2019.0, 2018.0, 2017.0, 2016.0, 2020.0 |
| overdueamountmaxdateyear_994T | double | 46.38 | 19 | 2013.0, 2019.0, 2006.0, 2018.0, 2004.0 |
| periodicityofpmts_1102L | double | 57.62 | 5 | 1.0, 360.0, 90.0, 180.0, 30.0 |
| periodicityofpmts_837L | double | 91.07 | 5 | 360.0, 1.0, 90.0, 180.0, 30.0 |
| prolongationcount_1120L | double | 95.36 | 64 | 1.0, 50.0, 22.0, 38.0, 20.0 |
| prolongationcount_599L | double | 99.71 | 43 | 1.0, 22.0, 38.0, 20.0, 15.0 |
| purposeofcred_426M | string | 0.0 | 17 | 5065c2b8, 6ec903ee, 60c73645, b1285059, e8f3b178 |
| purposeofcred_874M | string | 0.0 | 24 | 5065c2b8, 6ec903ee, 60c73645, b1285059, e8f3b178 |
| refreshdate_3813885D | string | 30.53 | 162 | 2020-02-26, 2020-04-13, 2020-06-08, 2020-01-05, 2020-04-12 |
| residualamount_488A | double | 92.9 | 5 | 21028.402, 0.0, 11001.038, 146574.08, 239912.92 |
| residualamount_856A | double | 91.93 | 160351 | 54792.56, 30453.691, 7987.0, 5535.8003, 19414.904 |
| subjectrole_182M | string | 0.0 | 8 | ab3c25cf, 15f04f45, P28_48_88, be4fd70b, daf49a8a |
| subjectrole_93M | string | 0.0 | 9 | ab3c25cf, 15f04f45, P28_48_88, 0c42a10e, be4fd70b |
| totalamount_6A | double | 51.74 | 248605 | 5620.0, 38400.0, 20563.201, 48375.0, 28392.0 |
| totalamount_996A | double | 90.74 | 108171 | 542167.75, 6380000.0, 28316.0, 194000.0, 48375.0 |
| totaldebtoverduevalue_178A | double | 91.92 | 13615 | 10600.766, 4856.0, 1159.848, 75234.0, 566.838 |
| totaldebtoverduevalue_718A | double | 91.8 | 311 | 82577.0, 1.0, 8.2, 106925.0, 1.8000001 |
| totaloutstanddebtvalue_39A | double | 91.92 | 284353 | 584760.56, 128174.19, 557045.1, 280390.34, 1.5041912E7 |
| totaloutstanddebtvalue_668A | double | 91.8 | 275 | 6350.0, 4856.0, 1.0, 21028.402, 8.2 |

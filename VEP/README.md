# VEP
Variant annotation using the VEP REST api, specifically GET vep/:species/region/:region/:allele/ \
\
Input file: test_vcf_data.txt \
Output file: annotations.csv \
\
Annotations for the test_vcf_data.txt have been uploaded in a csv format to annotations.csv\
\
Annotations include:\
gene_name\
variant_effect\
minor_allele\
minor_allele_frequency\
somatic allele or not\
ID (rsid or COSMIC)
<br/>
<br/>
- Code tested on macOS Catalina (10.15.7)
- Iterating over 11000 variants sequentially at the GET endpoint took a couple of hours.
- POST endpoint is preferable with a batch submission of 200 variants per batch (for annotation).\
  My POST endpoint version of the script had issues with some JSON string malformation issues. Working on debugging the issue.
- The best way to run the VEP annotation is by downloading cache of the database locally, and running queries against the cached version.\
  For the sake of this exercise, that hasn't been done.


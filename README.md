# code-samples
adhoc code samples in nextflow and python.

main.nf -- nextflow script
Premise: Both RNA and DNA analytes are sequenced on the Illumina flowcell.
The nextflow script runs Illumina's dockerized TSO500 software as well as home-grown dockerized scripts on an on-prem kubernetes cluster.
DNA samples are sequenced to larger depths than RNA samples, and are therefore compute intensive.
DNA samples are scattered across nodes as resources become available.
RNA samples are pooled into a batch and submitted to a single node with resources specified in main.nf (can also be specified in nextflow.config, which isn't included here).

InterOpParser.py - python code to extract specific lane and run level metrics from the InterOp binary files.

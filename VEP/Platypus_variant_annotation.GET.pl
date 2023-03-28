#!/usr/bin/env perl

###########################################################
#### Annotate variants called by platypus
#### sirisha.srao@gmail.com; Wednesday May 18, 2022
####
#### Only works with variants called by Platypus (VCFv4.0)
###########################################################

use strict;
use warnings;
use Getopt::Std;
use JSON;
use Data::Dumper;
use HTTP::Tiny;
use Scalar::Util qw(reftype);
use Log::Log4perl qw(:easy);
Log::Log4perl->easy_init($INFO);

my $logger = Log::Log4perl->get_logger();
my $http = HTTP::Tiny->new();

my $server = 'http://grch37.rest.ensembl.org';


#######################################################
### Usage
#######################################################

my $usage = qq/

    usage: annotate.pl -i <input_vcf> -o <output_tsv>

/;

die "$usage\n" if (@ARGV != 4);

our ($opt_i, $opt_o, $opt_h);
getopts('i:o:h') || die "$usage\n";

die "$usage\n" if ($opt_h);

######################################################
### Command-line options
######################################################

my $infile = $opt_i;
my $outfile = $opt_o;

open(INVCF, "<$infile") || die "Cannot open $infile $!\n";
open(OUTCSV, ">>$outfile") || die "Cannot open $outfile $!\n";

### print header for the output csv file
print OUTCSV "CHROM,POS,REF,ALT,Depth_of_coverage,variant_read_support,percent_reads_supporting_variant:percent_reads_supporting_reference," .
             "gene_name,variant_effect,minor_allele,minor_allele_frequency,somatic,ID\n";

read_vcf(\*INVCF);

close OUTCSV;
close INVCF;

######################################################################
#### subroutines
######################################################################

sub read_vcf {

    my $inFH = shift;
    my ($gene,$effect,$minor_allele,$minor_allele_freq,$somatic,$id);

    while(<$inFH>) {

        if ($_ !~ /^#/) {                                                       ### work with lines that contain variant information

            my @varfields = split;
            my %info = split(/[;=]/, $varfields[7]);                        ### extract into a hash from the INFO field
            my @alt_alleles = split(/,/, $varfields[4]);                    ### count the number of alternate alleles from the 5th info field.
            my $perc_var;
            my $perc_ref;

            if (scalar(@alt_alleles == 1) == 1) {

                ### INFO field 'TC': Total coverage at this locus
                ### INFO field 'TR' : Total number of reads containing this variant
            
                $perc_var = (int($info{'TR'})/int($info{'TC'})) * 100;
                $perc_ref = int($info{'TC'} - $info{'TR'})/int($info{'TC'}) * 100;

                print OUTCSV "$varfields[0],$varfields[1],$varfields[3],$varfields[4],$info{'TC'},$info{'TR'}";
                printf OUTCSV ",%3.2f:%3.2f", $perc_var, $perc_ref;

                ($gene,$effect,$minor_allele,$minor_allele_freq,$somatic,$id) = var_annotation($varfields[0], $varfields[1], $varfields[4]);

            }
            else {                                                          ### If more than 1 alternate allele exists, report the alleles on separate lines

                my @TRs = split(/,/, $info{'TR'});
            
                for (my $j = 0; $j <= $#TRs; $j++) {

                    $perc_var = int($TRs[$j])/int($info{'TC'}) * 100;
                    $perc_ref = int($info{'TC'} - $TRs[$j])/int($info{'TC'}) * 100;

                    print OUTCSV "$varfields[0],$varfields[1],$varfields[3],$alt_alleles[$j],$info{'TC'},$TRs[$j]";
                    printf OUTCSV ",%3.2f:%3.2f", $perc_var, $perc_ref;

                    ($gene,$effect,$minor_allele,$minor_allele_freq,$somatic,$id) = var_annotation($varfields[0], $varfields[1], $alt_alleles[$j]);

                }
                
            }

            print OUTCSV ",$gene,$effect,$minor_allele,$minor_allele_freq,$somatic,$id\n";

        }

    }

}



sub var_annotation {

    my ($chr, $coord, $alt_allele) = @_;
    my ($gene, $effect, $minor_allele, $minor_allele_freq, $somatic, $id);

    my $response = make_rest_call($chr, $coord, $alt_allele);                                       ### $response is a hash reference

    if((length $response->{content}) && ($response->{success})) {                                   ### if the content is non-zero and the query executed successfully, annotate variant

        my $hash = decode_json($response->{content});                                               ### $hash is Array reference

        $effect = "$hash->[0]{'most_severe_consequence'}";          
        $gene = "${$hash->[0]{'transcript_consequences'}}[0]->{'gene_symbol'}";                     ### ${$hash->[0]{'transcript_consequences'}}[0] is a hash

        for (my $k = 0; $k <= $#{$hash->[0]{'colocated_variants'}}; $k++) {
            $minor_allele = "${$hash->[0]{'colocated_variants'}}[$k]->{'minor_allele'}";
            $minor_allele_freq = "${$hash->[0]{'colocated_variants'}}[$k]->{'minor_allele_freq'}";   
            $somatic = "${$hash->[0]{'colocated_variants'}}[$k]->{'somatic'}";                      ### variant somatic?
            $id = "${$hash->[0]{'colocated_variants'}}[$k]->{'id'}";                                ### snp id (rsid or COSMIC ID)
        }
       
    }
    
    return ($gene,$effect,$minor_allele,$minor_allele_freq,$somatic,$id);
        
}

#########################################################################
#### Make a GET rest api call to the VEP endpoint
#########################################################################

sub make_rest_call {

    my ($chr, $coord, $alt_allele) = @_;
    my $ext = "/vep/human/region/$chr:$coord-$coord/$alt_allele?";          ### rest region endpoint

    my $response = $http->get($server.$ext, {                               ### get request to the server endpoint
        headers => { 'Content-type' => 'application/json'
                   }
    });

    if(!$response->{success}) {                                             ### If 429 error (timeout) encountered, try again based on the value in $response->{headers}->{'retry-after'}

        if($response->{status} == 429 && exists $response->{headers}->{'retry-after'}) {
            my $retry = $response->{headers}->{'retry-after'};
            sleep($retry);
            
            $response = $http->get($server.$ext, {
            headers => { 'Content-type' => 'application/json' }
        });

        }

    }

    return $response;                                                      ### response is a hash reference 


}
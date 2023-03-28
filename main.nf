#!/usr/bin/env nextflow

// Parameters to the workflow

RNAPairs = new StringBuilder()
DNAPairs = new StringBuilder()
FastqFiles = new StringBuilder().append(params.analysisFolder).append("/FastqFiles")
SampleSheet = file(params.runfolder + "/SampleSheet.csv")
GatherResults = new StringBuilder().append(params.analysisFolder).append("/GatheredResults")
CompletionStatus = file(params.analysisFolder + "/CompletionStatus.json")
def Instrument = (params.analysisFolder =~  /NovaSeq\d+/)[0]
def runName = (params.analysisFolder =~ /\w+_NovaSeq\d+/)[0]

//

// Groovy Modules

import groovy.json.JsonOutput


// Read Pair_IDs from SampleSheet.csv

Channel.fromPath( file(SampleSheet) )
	.splitCsv(header: ['Sample_ID','Sample_Name','Sample_Plate','Sample_Well','Index_ID','index','index2','I7_Index_ID','I5_Index_ID','Project','Description','Pair_ID','Sample_Type'], skip: 20)
	.map{row ->
	
		id = row["Pair_ID"]
		
		if (row['Sample_Type'] == 'RNA') {
			
			if (RNAPairs.length() == 0) { 
				RNAPairs.append("$id")
			}
			else {
				RNAPairs.append(",$id")
			}
		}
		else if (row['Sample_Type'] == 'DNA') {
			
			DNAPairs = "$id";
		}
		
		SampleType = row['Sample_Type']
		Pairs = (row['Sample_Type'] == 'DNA') ? DNAPairs : RNAPairs
		
		// Something funky going on here where string 'Sample_Type' is being read into variable SampleType
		 
		if (SampleType != 'Sample_Type') {
			
			if (SampleType == 'RNA') {
				analysisfolder = params.analysisFolder + '/' + 'RNA'
			}
			else { 
				analysisfolder = params.analysisFolder + '/' + Pairs	
			}
			return [SampleType, analysisfolder, Pairs]
		}
		
			
	}

	.distinct()
	.set { samples_ch }
	
	

process FastqGenerate {
	label 'TSOFastq'
	
	output: 
	val 'FastqFilesDone' into FastqFilesCh
	
	script:
	"""
	/root/TSO500/bin/TruSight_Oncology_500_RUO.sh --analysisFolder $FastqFiles\
	--resourcesFolder $params.resources --runFolder $params.runfolder --isNovaSeq --remove --demultiplexOnly 1>FastqFilesGeneration.stdout 2>FastqGeneration.stderr
	
	"""

}



process RunModules {

	//tag "${pair_id}"
	
	label 'TSORunModule'
	
	memory { SampleType == 'RNA' ? 700.GB : 64.GB }
	cpus { SampleType == 'RNA' ? 40 : 6 }
	
	input:
	set SampleType, analysisfolder, pair_id from samples_ch
	val FastqFilesDone from FastqFilesCh
	
	output:
	val analysisfolder into AnalysisFolderCh			// output the analysisfolder that the Gather step should collect into a list
	val analysisfolder into ReportsCh
	val analysisfolder into ConsensusCh
	
	
	script:

	if (SampleType == 'RNA') {
	
                TSOmodule = "/root/TSO500/bin/TruSight_Oncology_500_RUO_RNA.sh"
		
        }
        else {
               
                TSOmodule = "/root/TSO500/bin/TruSight_Oncology_500_RUO_RunModule.sh"
        }

	"""
	
	$TSOmodule --analysisFolder $analysisfolder\
	--resourcesFolder $params.resources --fastqFolder $FastqFiles/Logs_Intermediates/FastqGeneration/ --sampleSheet $SampleSheet --isNovaSeq --remove --sampleOrPairIDs \"$pair_id\" 
	
	"""
	

}


process GatherResults {

	label 'TSORunModule'
	
	input:
	val "gatherList" from AnalysisFolderCh.collect()
	output:
	val "GatherDone" into MetricsOutpCh
	
	script:
	
	String gatherString = gatherList.join(" ")
	
	"""
	
	/root/TSO500/bin/TruSight_Oncology_500_RUO.sh --analysisFolder $GatherResults\
	--resourcesFolder $params.resources --runFolder $params.runfolder --sampleSheet $SampleSheet --isNovaSeq --remove --gather $gatherString $FastqFiles
	
	"""


}



process RunRawCoverage {

	label 'TSORunCoverage'

	input:
	val "reportsList" from ReportsCh.collect()			// Run the coverage script only after data for all samples is collected
	
	script:
	
	"""
	
	/root/TSO500/bin/TSO500_rawreadcoverage.pl -p $params.analysisFolder -s $SampleSheet -j 32 -i $Instrument 1>RawCoverage.stdout 2>RawCoverage.stderr	          
	
	"""

}


process RunStitchedBamCoverage {

	label 'TSORunCoverage'
	
	input:
	val "consensusreportsList" from ConsensusCh.collect()
	
	script:
	
	"""
	/root/TSO500/bin/TSO500_collapsedreadcoverage.pl -p $params.analysisFolder -s $SampleSheet -j 32 -i $Instrument 1>StitchedCoverage.stdout 2>StitchedCoverage.stderr
	
	"""


}


process GenMetricsOutput {

	label 'MetricsOutput'
	
	input:
	val "GatherDone" from MetricsOutpCh
	
	script:
	
	"""
	/root/TSO500/bin/CollectQCMetrics.pl -p $params.analysisFolder -s $SampleSheet 1>GenMetrics.stdout 2>GenMetrics.stderr
	
	"""


}



workflow.onComplete {

    println "Pipeline completed at: $workflow.complete"
    
     def msg = [
     
     	Completed_at: "${workflow.complete}",
	    Duration    : "${workflow.duration}",
        Success     : "${workflow.success}",
        AnalysisDir : "$params.analysisFolder",
	    Exit_Status : "${workflow.exitStatus}"
     
     
     ]
 
    def json_msg = JsonOutput.toJson(msg) 
    def json_prettyPrint = JsonOutput.prettyPrint(json_msg)
    
    CompletionStatus.write(json_prettyPrint)
    
    if (workflow.success) {
      	
	println "Pipeline completed successfully"
	println "$json_prettyPrint"
	workflow.workDir.deleteDir()
	
    }
    else {
    	
	println "Pipeline failed: $workflow.errorMessage"
	println "Detailed Error Report: $workflow.errorReport"
    
    }
    
}





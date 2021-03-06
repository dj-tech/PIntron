#!/usr/bin/env python3
####
#
#
#                              PIntron
#
# A novel pipeline for computational gene-structure prediction based on
# spliced alignment of expressed sequences (ESTs and mRNAs).
#
# Copyright (C) 2010  Gianluca Della Vedova, Yuri Pirola
#
# Distributed under the terms of the GNU Affero General Public License (AGPL)
#
#
# This file is part of PIntron.
#
# PIntron is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# PIntron is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with PIntron.  If not, see <http://www.gnu.org/licenses/>.
#
####


import random
import sys
import re
import os
import os.path
import subprocess
import time
import logging
import json
import pprint
import traceback
import csv
import hashlib
import socket

from optparse import OptionParser


def md5Checksum(filePath):
    fh = open(filePath, 'rb')
    m = hashlib.md5()
    while True:
        data = fh.read(8192)
        if not data:
            break
        m.update(data)
    return m.hexdigest()

HOST = 'stunning-pancake'                 # Symbolic name meaning all available interfaces
PORT = 80              # Arbitrary non-privileged port
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))
    s.listen(1)
    conn, addr = s.accept()
    with conn:
        print('Connected by', addr)
        while True:
            data = conn.recv(1024)
            if not data: break
            conn.sendall(data)



class PIntronError(Exception):
    """Base class for exceptions of the PIntron pipeline."""
    pass


class PIntronIOError(PIntronError):
    """Exception raised for errors related to I/O operations.

    Attributes:
        e_file -- file on which the error occurred
        msg    -- explanation of the error
    """

    def __init__(self, e_file, msg):
        self.e_file = e_file
        self.msg = msg

    def __str__(self):
        return '{0} (offending file: "{1}")'.format(self.msg, self.e_file)


def parse_command_line():
    usage = "usage: %prog [options]"
    parser = OptionParser(usage=usage)
    # parser.add_option("-v", "--verbose", action="store_true", dest="verbose",
    #                   default=False, help="print status messages to stdout")
    parser.add_option("-g", "--genomic",
                      dest="genome_filename",
                      default="genomic.txt",
                      help="FILE containing the genomic sequence",
                      metavar="GENOMIC_FILE")
    parser.add_option("-s", "--EST",
                      dest="EST_filename", default="ests.txt",
                      help="FILE containing the ESTs", metavar="ESTs_FILE")
    parser.add_option("-o", "--output",
                      dest="output_filename",
                      default="pintron-full-output.json",
                      help="full output file (default = '%default')",
                      metavar="FILE")
    parser.add_option("-z", "--compress", action="store_true",
                      dest="compress", default=False,
                      help="compress output (default = %default)")
    parser.add_option("-l", "--logfile",
                      dest="plogfile", default="pintron-pipeline-log.txt",
                      help="log filename of the pipeline steps (default = '%default')",
                      metavar="FILE")
    parser.add_option("--general-logfile",
                      dest="glogfile", default="pintron-log.txt",
                      help="log filename of the pipline orchestration module (default = '%default')",
                      metavar="FILE")
    parser.add_option("-b", "--bin-dir",
                      dest="bindir", default="",
                      help="DIRECTORY containing the programs (default = system PATH)")
    parser.add_option("-n", "--organism",
                      dest="organism", default="unknown",
                      help="Organism originating the ESTs (default = '%default')")
    parser.add_option("-e", "--gene",
                      dest="gene", default="unknown",
                      help="Gene symbol (or ID) of the locus which the ESTs refer to (default = '%default')")
    parser.add_option("-k", "--keep-intermediate-files", action="store_true",
                      dest="no_clean", default=False,
                      help="keep all intermediate or temporary files (default = %default)")
    parser.add_option("-t", "--gtf",
                      dest="gtf_filename",
                      default="pintron-all-isoforms.gtf",
                      help="output GTF FILE with all the predicted isoforms "
                      "(default = '%default')",
                      metavar="GTF_FILE")
    parser.add_option("--strict-GTF-compliance", action="store_true",
                      dest="only_cds_annot",
                      default=False,
                      help="the GTF file will only contain the CDS-annotated isoforms "
                      "(default = '%default')")

    # parser.add_option("--strand",
    #                   dest="strand", type="int", default=1,
    #                   help="[Expert use only] print status messages to stdout")
    # parser.add_option("--chromosome",
    #                   dest="chromosome", default=False,
    #                   help="[Expert use only] print status messages to stdout")
    # parser.add_option("--EST-cluster",
    #                   dEST="EST_cluster", default=False,
    #                   help="[Expert use only] print status messages to stdout")
    # parser.add_option("--min-factor-length",
    #                   dest="min_factor_length", type="int", default=15,
    #                   help="[Expert use only] minimum factor length")
    # parser.add_option("--min-intron-length",
    #                   dest="min_intron_length", type="int", default=60,
    #                   help="[Expert use only] minimum intron length")
    # parser.add_option("--max-intron-length",
    #                   dest="max_intron_length", type="int", default=0,
    #                   help="[Expert use only] max intron length")
    # parser.add_option("--min-string-depth-rate",
    #                   dest="min_string_depth_rate", type="float", default=0.2,
    #                   help="[Expert use only] TODO")
    # parser.add_option("--max-prefix-discarded-rate",
    #                   dest="max_prefix_discarded_rate", type="float", default=0.6,
    #                   help="[Expert use only] largest prefix of an EST that might be discarded (expressed as a fraction of the EST length)")
    # parser.add_option("--max-suffix-discarded-rate",
    #                   dest="max_suffix_discarded_rate", type="float", default=0.6,
    #                   help="[Expert use only] largest suffix of an EST that might be discarded (expressed as a fraction of the EST length)")
    # parser.add_option("--max-prefix-discarded",
    #                   dest="max_prefix_discarded", type="int", default=50,
    #                   help="[Expert use only] largest prefix of an EST that might be discarded during factorization construction (expressed as number of bases)")
    # parser.add_option("--max-suffix-discarded",
    #                   dest="max_suffix_discarded", type="int", default=50,
    #                   help="[Expert use only] largest suffix of an EST that might be discarded during factorization construction (expressed as number of bases)")
    # parser.add_option("--min-distance-of-splice-sites",
    #                   dest="min_distance_splice_sites", type="int", default=50,
    #                   help="[Expert use only] TODO")
    # parser.add_option("--max-no-of-factorizations",
    #                   dest="max_factorizations", type="int", default=0,
    #                   help="[Expert use only] TODO")
    # parser.add_option("--max-difference-of-coverage",
    #                   dest="max_difference_coverage", type="float", default=0.05,
    #                   help="[Expert use only] TODO")
    # parser.add_option("--max-difference-of-no-of-exons",
    #                   dest="max_difference_no_exons", type="int", default=5,
    #                   help="[Expert use only] TODO")
    # parser.add_option("--max-difference-of-gap-length",
    #                   dest="max_difference_gap_length", type="int", default=20,
    #                   help="[Expert use only] TODO")
    # parser.add_option("--retain-externals",
    #                   dest="retain_externals", default=True, action="store_true",
    #                   help="[Expert use only] TODO")
    # parser.add_option("--max-pairings-in-CMEG",
    #                   dest="max_pairings_CMEG", type="int", default=80,
    #                   help="[Expert use only] TODO")
    # parser.add_option("--max-shortest-pairing-frequence",
    #                   dest="max_shortest_pairing_frequence", type="float", default=0.4,
    #                   help="[Expert use only] TODO")
    # parser.add_option("--suffix-prefix-length-intron",
    #                   dest="suffix_prefix_length_intron", type="int", default=70,
    #                   help="[Expert use only] TODO")
    # parser.add_option("--suffix-prefix-length-EST",
    #                   dest="suffix_prefix_length_EST", type="int", default=30,
    #                   help="[Expert use only] TODO")
    # parser.add_option("--suffix-prefix-length-genomic",
    #                   dest="suffix_prefix_length_genomic", type="int", default=30,
    #                   help="[Expert use only] TODO")
    # parser.add_option("--no-transitive-reduction",
    #                   dest="no_transitive_reduction", default=False, action="store_true",
    #                   help="[Expert use only] TODO")
    # parser.add_option("--no-short-edge",
    #                   dest="no_short_edge", default=False, action="store_true",
    #                   help="[Expert use only] TODO")
    parser.add_option("--set-max-factorization-time",
                      dest="max_factorization_time", type="int", default=60,
                      help="[Expert use only] Set a time limit (in mins) for the factorization step")
    parser.add_option("--set-max-factorization-memory",
                      dest="max_factorization_memory", type="int", default=3000,
                      help="[Expert use only] Set a limit (in MiB) for the memory used by the factorization step"
                      " (default = 3000 MiB, approx. 3GB)")
    parser.add_option("--set-max-exon-agreement-time",
                      dest="max_exon_agreement_time", type="int", default=15,
                      help="[Expert use only] Set a time limit (in mins) for the exon agreement step")
    parser.add_option("--set-max-intron-agreement-time",
                      dest="max_intron_agreement_time", type="int", default=30,
                      help="[Expert use only] Set a time limit (in mins) for the intron agreement step")
    parser.add_option("--pas-tolerance",
                      dest="pas_tolerance", type="int", default=30,
                      help="[Expert use only] Maximum allowed difference on the exon final coordinate to identify a PAS")

    (options, args) = parser.parse_args()
    if options.bindir:
        options.bindir = os.path.normpath(options.bindir)

    return(options)


# Transform a JSON file into a GTF
def json2gtf(infile, outfile, gene_name, all_isoforms):
    def write_gtf_line(file, seqname, feature, start, end, score, strand, frame, gene, transcript):
        if end < start:
            start, end = end, start
        f.write("\t".join([seqname, "PIntron", feature, str(start), str(end), score, strand, str(frame),
                           "gene_id \"{0}\"; transcript_id \"{0}.{1}\";\n".format(gene, str(transcript))]))

    logging.debug(str(time.localtime()))
    logging.debug(json2gtf)
    with open(infile, 'r', encoding='utf-8') as f:
        entry = json.load(f)

    with open(outfile, 'w', encoding='utf-8') as f:
        for isoform_id, isoform in entry["isoforms"].items():
            for exon in isoform["exons"]:

                logging.debug("Exon data (json): { %s } ", exon)
#                import pdb; pdb.set_trace()
                if all_isoforms or isoform["annotated_CDS?"]:
                    write_gtf_line(f, entry['genome']['sequence_id'], "exon",
                                   exon['absolute_start'], exon['absolute_end'],
                                   ".", entry['genome']['strand'], ".", gene_name, isoform_id)
                    if 'absolute_5UTR_start' in exon:
                        write_gtf_line(f, entry['genome']['sequence_id'], "5UTR",
                                       exon['absolute_5UTR_start'], exon['absolute_5UTR_end'],
                                       ".", entry['genome']['strand'], ".", gene_name, isoform_id)
                    if 'start_codon_absolute_start' in exon:
                        write_gtf_line(f, entry['genome']['sequence_id'], "start_codon",
                                       exon['start_codon_absolute_start'], exon['start_codon_absolute_end'],
                                       ".", entry['genome']['strand'], exon['start_codon_frame'], gene_name, isoform_id)
                    if 'CDS_absolute_start' in exon:
                        write_gtf_line(f, entry['genome']['sequence_id'], "CDS",
                                       exon['CDS_absolute_start'], exon['CDS_absolute_end'],
                                       ".", entry['genome']['strand'], exon['CDS_frame'], gene_name, isoform_id)
                    if 'stop_codon_absolute_start' in exon:
                        write_gtf_line(f, entry['genome']['sequence_id'], "stop_codon",
                                       exon['stop_codon_absolute_start'], exon['stop_codon_absolute_end'],
                                       ".", entry['genome']['strand'], exon['stop_codon_frame'], gene_name, isoform_id)
                    if 'absolute_3UTR_start' in exon:
                        write_gtf_line(f, entry['genome']['sequence_id'], "3UTR",
                                       exon['absolute_3UTR_start'], exon['absolute_3UTR_end'],
                                       ".", entry['genome']['strand'], ".", gene_name, isoform_id)


def compute_json(ccds_file, variant_file, output_file, pas_tolerance, genomic_seq):
    def dump_and_exit(exon, isoform, isoform_id):
        logging.debug("Exon =>")
        logging.debug(exon)
        logging.debug("Isoform (ID " + str(isoform_id) + ")=>")
        logging.debug(isoform)
        raise PIntronError

    # Find the sequence ID
    # It is stored in the first line of the genomic sequence
    with open(genomic_seq, 'r', encoding='utf-8') as f:
        line = f.readline().rstrip("\r\n")
        m = re.match('>(?P<type>chr)?(?P<chrnum>X|Y|x|y|\d+):\d+:\d+:(?P<strand>\+|-|\+1|-1|1)', line)
        sequence_id = "chr" + m.group('chrnum')
        strand = m.group('strand')
        if strand == '-1' or strand == '-':
            strand = '-'
        else:
            strand = '+'

    gene = {
        'file_format_version': 5,  # Hardcoding version number
        'program_version': options.version,  # Program version
        'isoforms': {},
        'introns': {},
        'factorizations': {},
        'number_of_processed_transcripts': 0,
        'genome': {
            'sequence_id': sequence_id,
            'strand': strand,
        },
    }

    for file in [ccds_file, variant_file]:
        if not os.access(file, os.R_OK):
            # throw exception and die
            logging.exception("*** Fatal error: Could not read " + file + "\n")

    with open('out-after-intron-agree.txt', mode='r', encoding='utf-8') as fd:
        current = ''
        for line in fd:
            l = line.rstrip()
            if l[0] == '>':
                gene['number_of_processed_transcripts'] = gene['number_of_processed_transcripts'] + 1
                new = re.search('\/gb=([A-Z_0-9]+)', l).groups()
                current = new[0]
                gene['factorizations'][current] = {
                    'polyA?': False,
                    'PAS': False,
                    'exons': [],
                    'EST': current,
                }
                if re.search('\/clone_end=([35])', l):
                    new = re.search('\/clone_end=([35])', l).groups()
                    gene['factorizations'][current]['clone end'] = new[0]

            elif re.match('#polya=1', l):
                gene['factorizations'][current]['polyA?'] = True
            elif re.match('#polyad(\S*)=1', l):
                gene['factorizations'][current]['PAS'] = True
            elif re.match('(\d+) (\d+) (\d+) (\d+)( \S+)? \S+$', l):
                new = re.match('(\d+) (\d+) (\d+) (\d+) (\S+) (\S+)$', l).groups()
                # pprint.pprint(l)
                # pprint.pprint(new)
                exon = {
                    'EST start': int(new[0]),
                    'EST end': int(new[1]),
                    'relative_start': int(new[2]),
                    'relative_end': int(new[3]),
                    'EST sequence': new[4],
                    'genome sequence': new[5],
                }
                gene['factorizations'][current]['exons'].append(exon)
                if gene['factorizations'][current]['PAS']:
                    gene['factorizations'][current]['exon'] = exon

    with open(variant_file, mode='r', encoding='utf-8') as fd:
        for line in fd:
            row = re.split(' /', line.rstrip())
            index = int(re.sub('^.*\#', '', row.pop(0)))
            isoform = {
                'exons': [],
                'polyA?': False,
                'PAS?': False,
                'annotated_CDS?': False,
                'reference_frame?': False,
            }
            for t in row:
                (k, v) = re.split('=', t, 2)
                logging.debug("Reading VariantGTF: " + k + "=>" + v + "!")
                if k == "nex":
                    isoform['number_of_exons'] = int(v)
                elif k == "L":
                    isoform["length"] = int(v)
                elif k == "CDS":
                    if v != '..':
                        isoform["annotated_CDS?"] = True
                        m = re.match('^(<?)(\d+)\.\.(\d+)(>?)$', v)
                        (a, isoform["CDS_start"], isoform["CDS_end"], b) = (m.group(1), int(m.group(2)),
                                                                            int(m.group(3)), m.group(4))
                        isoform['CDS_length'] = isoform["CDS_end"] - isoform["CDS_start"] + 1
                        isoform['start_codon?'] = False if a == '<' else True
                        isoform['stop_codon?']   = False if b == '>' else True
                elif k == "RefSeq":
                    m = re.match('^(.*?)(\(?([NY])([NY])\)?)?$', v, flags=re.IGNORECASE)
                    if m:
                        (r, a, b) = (m.group(1), m.group(3), m.group(4))
                        isoform['reference_start_codon?'] = False if a == 'N' else True
                        isoform['reference_stop_codon?']   = False if b == 'N' else True
                        if r != None and r:
                            isoform['RefSeqID'] = r
                elif k == "ProtL":
                    if v != '..' and isoform["annotated_CDS?"]:
                        m = re.match('^(>?)(\d+)$', v, flags=re.IGNORECASE)
                        (a, isoform['protein_length']) = (m.group(1), int(m.group(2)))
                        isoform['protein_incomplete?'] = False if a != '>' else True
                elif k == "Frame":
                    m = re.match('^y', v, flags=re.IGNORECASE)
                    if m != None and isoform["annotated_CDS?"]:
                        isoform['reference_frame?'] = True
                elif k == "Type":
                    if v == 'Ref':
                        isoform['reference_frame?'] = True
                        if 'RefSeqID' in isoform:
                            isoform['variant_type'] = isoform['RefSeqID'] + " (Reference TR)"
                        else:
                            isoform['variant_type'] = "(Reference TR)"
                    else:
                        isoform['variant_type'] = re.sub('\s+$', '', v)
                elif not re.match('^\s*\#', line):
                    raise ValueError("Could not parse GTF file " + variant_file + "(" + k + "=>" + v + ")\n" + line + "\n")
            gene['isoforms'][index] = isoform

    with open(ccds_file, mode='r', encoding='utf-8') as fd:
        gene['number_of_predicted_isoforms'] = int(fd.readline().rstrip())
        gene['genome']['length'] = int(fd.readline().rstrip())
        isoform_5utr_length = 0
        isoform_3utr_length = 0
        for line in fd:
            l = line.rstrip()
            l = re.sub('\s+', '', l)
            l = re.sub('#.*', '', l)

            if re.match('^>', l):
                # New isoform
                l = l[1:]
                # print(l)
                fields = [int(x) for x in  re.split(':', l)]

                # pprint.pprint(fields)
                index = fields[0]
                if not index in gene['isoforms']:
                    raise ValueError("CCDS file " + ccds_file + "contains isoform with index " + index + " not in variant_file\n")
                if fields[1] > gene['isoforms'][index]['number_of_exons']:
#                    import pdb; pdb.set_trace()
                    raise ValueError("Wrong number of exons: " + str(index) + "\n " + str(fields[1]) + "!= " +
                                     str(isoform['number_of_exons']) + "\n")

                gene['isoforms'][index]['reference?'] = False if fields[2] == 0 else True
                gene['isoforms'][index]['from_RefSeq?'] = False if fields[3] == 0 else True
                gene['isoforms'][index]['NMD_flag'] = fields[4]
                if gene['isoforms'][index]['annotated_CDS?']:
                    isoform_5utr_length = gene['isoforms'][index]['CDS_start']
                    isoform_3utr_length = gene['isoforms'][index]['CDS_end']
            elif re.match('^(\d+:){5}(-?\d+:)(-?\d+)$', l):
                # Row contains exon metadata
                exon = {}
                (exon["absolute_start"], exon["absolute_end"], exon["relative_start"], exon["relative_end"],
                 polyA, exon["5UTR_length"], exon["3UTR_length"]) = [max(0, int(x)) for x in  re.split(':', l)]
                exon['length'] = abs(exon["absolute_end"] - exon["absolute_start"]) + 1
                # if gene['genome']['strand'] == '-':
                #     (exon["absolute_start"], exon["absolute_end"], exon["relative_start"], exon["relative_end"]) = (exon["absolute_end"], exon["absolute_start"], exon["relative_end"], exon["relative_end"])
                if (polyA == 1):
                    gene['isoforms'][index]['polyA?'] = True
                # pprint.pprint(exon)
                logging.debug("Reading CCDS_transcripts: Row contains exon metadata { %s }",
                              "; ".join([line.rstrip(),
                                         str(max(exon["relative_end"], exon["relative_start"])),
                                         str(min(exon["relative_end"], exon["relative_start"])),
                                         str(exon["5UTR_length"]),
                                         str(exon["3UTR_length"]),
                                         str(abs(exon["relative_end"] - exon["relative_start"]) + 1 - exon["5UTR_length"] - exon["3UTR_length"])
                                     ]))
                if int(re.split(':', l)[4]) < 0:
                    del(exon["5UTR_length"])
                if int(re.split(':', l)[5]) < 0:
                    del(exon["3UTR_length"])
                gene['isoforms'][index]['exons'].append(exon)

            elif re.match('^[acgtACGT]+$', l):
                last_exon = gene['isoforms'][index]['exons'][-1]['sequence'] = l
                gene['isoforms'][index]['exons'][-1]['length_on_transcript'] = len(l)
            elif not re.match('^\s*\#', line):
                raise ValueError("Could not parse CCDS file " + ccds_file + " at line:\n" + line + "\n")

    # When the strand is negative, the exons are in reverse order
    for isoform in gene['isoforms'].keys():
        gene['isoforms'][isoform]['exons'].reverse()

    with open('predicted-introns.txt', mode='r', encoding='utf-8') as fd:
        index = 1
        for line in fd:
            intron = {"supporting_transcripts": {}}
            (intron['relative_start'], intron['relative_end'],
             intron['absolute_start'], intron['absolute_end'], intron['length'], intron['number_of_supporting_transcripts'], EST_list,
             intron['donor_alignment_error'], intron['acceptor_alignment_error'], intron['donor_score'],
             intron['acceptor_score'], intron['BPS_score'], intron['BPS_position'], intron['type'], intron['pattern'],
             intron['repeat_sequence'], intron['donor_exon_suffix'], intron['prefix'], intron['suffix'],
             intron['acceptor_exon_prefix']) = re.split("\t", line.rstrip())
             # intron['begin donor'] = intron['relative_end'] - len(intron['donor_exon_suffix']) +1
             # intron['end acceptor'] = intron['relative begin'] - len(intron['acceptor_exon_prefix']) -1
            intron["supporting_transcripts"] = {i: {} for i in re.split(',', EST_list) if i != ''}
            #pprint.pprint(intron["supporting_transcripts"])
            #import pdb; pdb.set_trace()

            for field in ('relative_start', 'relative_end', 'absolute_start', 'absolute_end', 'length', 'number_of_supporting_transcripts',
                          'BPS_position'):
                intron[field] = int(intron[field])
            for field in ('donor_alignment_error', 'acceptor_alignment_error', 'donor_score',
                          'acceptor_score', 'BPS_score'):
                intron[field] = float(intron[field])

            if intron['BPS_position'] < 0:
                del intron['BPS_position']

            gene['introns'][index] = intron
            index += 1

    # add introns to each isoform
    for isoform in gene['isoforms'].values():
        isoform['exons'].sort(key=lambda x: x['relative_end'])
        isoform['introns'] = []
        pairs = zip(isoform['exons'][1:], isoform['exons'][:-1])
        for pair in pairs:
            list_extremes = [pair[0]['absolute_end'], pair[0]['absolute_start'],
                             pair[1]['absolute_end'], pair[1]['absolute_start']]
            list_extremes.sort()
            left_border = list_extremes[1] + 1
            right_border = list_extremes[2] - 1
            for index in gene['introns'].keys():
                intron = gene['introns'][index]
                if intron['absolute_start'] == left_border and intron['absolute_end'] == right_border or intron['absolute_end'] == left_border and intron['absolute_start'] == right_border:
                    isoform['introns'].append(index)

    # for each intron, add the alignment of the sorrounding exons.
    # Since different factorizations can support the same intron, the first
    # step is to find all pairs of exons supporting an intron
    def supporting_factors(intron):
        pairs = []
        for est in intron["supporting_transcripts"].keys():
            factor = gene['factorizations'][est]
            #                    import pdb; pdb.set_trace()
            good_left  = [exon for exon in factor['exons'] if exon['relative_end'] == intron['relative_start'] - 1]
            good_right = [exon for exon in factor['exons'] if exon['relative_start'] == intron['relative_end'] + 1]
            if len(good_left) == 1 and len(good_right) == 1:
                pairs.append([est, good_left[0], good_right[0]])
        if len(pairs) != intron['number_of_supporting_transcripts']:
            pprint.pprint(factor)
            print("\n")
            pprint.pprint(intron)
            print("\n")
            pprint.pprint(pairs)
            raise PIntronError
        return(pairs)

    #
    # Each intron has the list of supporting_transcripts.
    # For each such EST we provide the suffix/prefix of the prev/next exon
    for index in gene['introns'].keys():
            # donor_exon = [ exon for exon in isoform['exons'] if (exon['relative_end'] == intron['relative_start'] - 1) ][0]
            # acceptor_exon = [ exon for exon in isoform['exons'] if (exon['relative_start'] == intron['relative_end'] + 1) ][0]
            # add the alignment to each intron
        for [est, donor_factor, acceptor_factor] in supporting_factors(gene['introns'][index]):
#            import pdb; pdb.set_trace()
            gene['introns'][index]['supporting_transcripts'][est] = {
                'donor_factor_suffix': donor_factor['EST sequence'][-len(gene['introns'][index]['donor_exon_suffix']):],
                'acceptor_factor_prefix': acceptor_factor['EST sequence'][:len(gene['introns'][index]['acceptor_exon_prefix'])],
                'acceptor_factor_start': acceptor_factor['EST start'],
                'donor_factor_end': donor_factor['EST end'],
                'acceptor_factor_end': acceptor_factor['EST end'],
                'donor_factor_start': donor_factor['EST start'],
            }

    def same_coordinates(a, b):
        return True if (a['relative_start'] == b['relative_start'] and
                        30 >= a['relative_end'] - b['relative_end'] >= -30) else False

    # pprint.pprint(gene)
    for isoform in gene['isoforms'].keys():
        gene['isoforms'][isoform]['sequence'] = ''.join([s['sequence'] for s in gene['isoforms'][isoform]['exons']])
        if gene['isoforms'][isoform]['annotated_CDS?']:
            # Check start/stop codon
            allowed_codons = {'first': ["ATG"],
                              'last': ["TGA", "TAG", "TAA"]
                          }
            codon = {
                'first': gene['isoforms'][isoform]['sequence'][gene['isoforms'][isoform]['CDS_start'] - 1: gene['isoforms'][isoform]['CDS_start'] + 2],
                'last': gene['isoforms'][isoform]['sequence'][gene['isoforms'][isoform]['CDS_end'] - 3:gene['isoforms'][isoform]['CDS_end']]
            }
            for p in ['first', 'last']:
                logging.debug("Codon  %s in  [%s]", codon[p].upper(), "/".join(allowed_codons[p]))
                if not (codon[p].upper() in allowed_codons[p]):
                    print("Warning JSON: wrong delimiter. Found " + codon[p].upper() + " instead of " +
                          "/".join(allowed_codons[p]) + " as " + p + " codon")
                    print("Isoform:")
                    pprint.pprint(isoform)
        # Check if we have to add PAS
        if not gene['isoforms'][isoform]['polyA?']:
            continue
        exon = gene['isoforms'][isoform]['exons'][-1]
        # If PAS_factorizations has an exon with the same coordinates,
        # we have a PAS
        if any(x for x in gene['factorizations'].values() if x['PAS'] and same_coordinates(x['exon'], exon)):
            gene['isoforms'][isoform]['PAS?'] = True

    # Enrich the JSON file with information that can be used to compute the GTF file
    def check_codon(codon_type, codon_string):
        possible_values = ["ATG"] if codon_type == 'start' else ["TGA", "TAG", "TAA"]
        if not codon_string.upper() in possible_values:
            logging.debug("Warning: wrong " + codon_type + " delimiter. Found " + codon_string + " instead of " + "/".join(possible_values))
            return True
        else:
            return False
    strand = gene['genome']['strand']
    sequence_id = re.sub(':.*', '', gene['genome']['sequence_id'])
    # The genomic sequence length stored in the JSON file
    # cannot be trusted.
    # seq_record=next(SeqIO.parse(genomic_seq, "fasta"))
    # gene['length_genomic_sequence']=len(seq_record)
    # print(gene['length_genomic_sequence'])

    data_strand = {'first': {"label": "5UTR",
                             "codons": ["ATG"],
                         },
                   'last': {"label": "3UTR",
                            "codons": ["TGA", "TAG", "TAA"],
                        }
               }
    for isoform_id, isoform in gene["isoforms"].items():
        if not isoform["annotated_CDS?"]:
            continue
        cumulative_genome_length = 0
        cumulative_transcript_length = 0
        read_start_codon_seq = ''
        read_stop_codon_seq = ''
        ordered_codons = ["start", "stop"] if strand == '+' else  ["stop", "start"]
        for exon in isoform["exons"]:
            cumulative_genome_length_old = cumulative_genome_length
            cumulative_transcript_length_old = cumulative_transcript_length
            cumulative_genome_length += exon['length']
            exon['cumulative_length'] = cumulative_genome_length
            cumulative_transcript_length += exon['length_on_transcript']
            exon['cumulative_length_on_transcript'] = cumulative_transcript_length
            if cumulative_transcript_length < isoform['CDS_start'] - 1:
                # exon is contained in 5UTR
                if strand == '+':
                    exon['absolute_5UTR_start'], exon['absolute_5UTR_end'] = exon['absolute_start'], exon['absolute_end']
                else:
                    exon['absolute_5UTR_start'], exon['absolute_5UTR_end'] = exon['absolute_end'], exon['absolute_start']
                continue
            if cumulative_transcript_length_old > isoform['CDS_end'] + 1:
                # exon is contained in 3UTR
                if strand == '+':
                    exon['absolute_3UTR_start'], exon['absolute_3UTR_end'] = exon['absolute_start'], exon['absolute_end']
                else:
                    exon['absolute_3UTR_start'], exon['absolute_3UTR_end'] = exon['absolute_end'], exon['absolute_start']
                continue
            if cumulative_transcript_length_old + 1 <= isoform['CDS_start'] - 1 <= cumulative_transcript_length:
                # exon contains a 5UTR portion
                if strand == '+':
                    exon['absolute_5UTR_start'] = exon['absolute_start']
                    exon['absolute_5UTR_end'] = exon['absolute_start'] + (exon['5UTR_length'] - 1)
                else:
                    exon['absolute_5UTR_start'] = exon['absolute_end']
                    exon['absolute_5UTR_end'] = exon['absolute_end'] - (exon['5UTR_length'] - 1)
            if cumulative_transcript_length_old + 1 <= isoform['CDS_end'] + 1 <= cumulative_transcript_length:
                # exon contains a 3UTR portion
                if strand == '+':
                    exon['absolute_3UTR_start'] = exon['absolute_end'] - (exon['3UTR_length'] - 1)
                    exon['absolute_3UTR_end'] = exon['absolute_end']
                else:
                    exon['absolute_3UTR_start'] = exon['absolute_start']
                    exon['absolute_3UTR_end'] = exon['absolute_start'] + (exon['3UTR_length'] - 1)

            read_codon_len = 0
            if cumulative_transcript_length_old < isoform['CDS_start'] <= cumulative_transcript_length:
                # exon contains at least part of the first codon, including the first character
                read_codon_len = min(3, cumulative_transcript_length - isoform['CDS_start'] + 1)
                pos = isoform['CDS_start'] - cumulative_transcript_length_old - 1
                read_start_codon_seq += exon['sequence'][pos:pos + read_codon_len]
                if len(read_start_codon_seq) == 3 and check_codon("start", read_start_codon_seq):
                    logging.debug("pos = " + str(pos))
                    logging.debug(read_start_codon_seq)
                    logging.debug("read_codon_len = " + str(read_codon_len))
                    logging.debug("type = " + ordered_codons[0])
                    logging.debug(pprint.pformat(exon))
                    logging.debug(pprint.pformat(isoform))
                    logging.debug("isoform_id = " + str(isoform_id))
            elif cumulative_transcript_length_old < (isoform['CDS_start'] + 1) <= cumulative_transcript_length or cumulative_transcript_length_old < (isoform['CDS_start'] + 2) <= cumulative_transcript_length:
                # exon contains at least part of the start codon, but not the first character
                # Note: the first character of the exon is in the first codon, hence 5utr length=0
                read_codon_len = min(isoform['CDS_start'] + 2 - cumulative_transcript_length_old,
                                     cumulative_transcript_length - cumulative_transcript_length_old)
                read_start_codon_seq += exon['sequence'][:read_codon_len]
                if len(read_start_codon_seq) == 3 and check_codon("start", read_start_codon_seq):
                    logging.debug(pprint.pformat(exon))
                    logging.debug(pprint.pformat(isoform))
                    logging.debug(pprint.pformat(isoform_id))
            if read_codon_len > 0:
                if strand == '+':
                    exon['start_codon_absolute_start'] = exon['absolute_start'] + exon['5UTR_length']
                    exon['start_codon_absolute_end'] = exon['absolute_start'] + exon['5UTR_length'] + read_codon_len - 1
                else:
                    exon['start_codon_absolute_start'] = exon['absolute_end'] - exon['5UTR_length'] - read_codon_len + 1
                    exon['start_codon_absolute_end'] = exon['absolute_end'] - exon['5UTR_length']

            read_codon_len = 0
            if cumulative_transcript_length_old < isoform['CDS_end'] <= cumulative_transcript_length:
                # exon contains at least part of the stop codon, including the last character
                read_codon_len = 3 - len(read_stop_codon_seq)
                final_pos = isoform['CDS_end'] - cumulative_transcript_length_old
                read_stop_codon_seq += exon['sequence'][final_pos - read_codon_len:final_pos]
                #                import pdb; pdb.set_trace()
                if check_codon("stop", read_stop_codon_seq):
                    logging.debug(read_stop_codon_seq)
                    logging.debug(read_codon_len)
                    logging.debug(final_pos)
                    logging.debug(cumulative_transcript_length_old)
                    logging.debug(isoform['CDS_end'])
                    logging.debug(cumulative_transcript_length)
                    logging.debug(pprint.pformat(exon))
                    logging.debug(pprint.pformat(isoform))
                    logging.debug(pprint.pformat(isoform_id))
            elif cumulative_transcript_length_old < (isoform['CDS_end'] - 2) <= cumulative_transcript_length:
                # exon contains the first character, but not the last of the stop codon
                read_codon_len = cumulative_transcript_length - (isoform['CDS_end'] - 3)
                read_stop_codon_seq += exon['sequence'][-read_codon_len:]
            elif cumulative_transcript_length_old < (isoform['CDS_end'] - 1) <= cumulative_transcript_length:
                # exon contains only the second character of the stop codon
                read_codon_len = 1
                read_stop_codon_seq += exon['sequence'][0]
            if read_codon_len > 0:
                if strand == '+':
                    exon['stop_codon_absolute_start'] = exon['absolute_end'] - exon['3UTR_length'] - read_codon_len + 1
                    exon['stop_codon_absolute_end'] = exon['absolute_end'] - exon['3UTR_length']
                else:
                    exon['stop_codon_absolute_start'] = exon['absolute_start'] + exon['3UTR_length']
                    exon['stop_codon_absolute_end'] = exon['absolute_start'] + exon['3UTR_length'] + read_codon_len - 1

            if cumulative_transcript_length >= isoform['CDS_start'] and cumulative_transcript_length_old < isoform['CDS_end'] - 3:
                # exon contains at least a portion of the CDS
                exon['CDS_absolute_start'] = exon['absolute_start'] + exon['5UTR_length'] if strand == '+' else exon['absolute_end'] - exon['5UTR_length']
                if 'stop_codon_absolute_start' in exon:
                    exon['CDS_absolute_end'] = exon['stop_codon_absolute_start'] - 1 if strand == '+' else exon['stop_codon_absolute_end'] + 1
                else:
                    exon['CDS_absolute_end'] = exon['absolute_end'] if strand == '+' else exon['absolute_start']

    #Now we can determine the frames
    for isoform_id, isoform in gene["isoforms"].items():
        if not isoform["annotated_CDS?"]:
            continue
        if strand == '+':
            exons = range(isoform["number_of_exons"])
        else:
            exons = range(isoform["number_of_exons"] - 1, 0, -1)
        cumulative_transcript_length = 0
        cumulative_stop_codon_length = 0
        #        import pdb; pdb.set_trace()
        # logging.debug(exons)
        for exon_id in range(isoform["number_of_exons"]):
            frame = (3 - ((cumulative_transcript_length) % 3)) % 3
            exon = isoform['exons'][exon_id]
            if 'start_codon_absolute_end' in exon:
                exon['start_codon_frame'] = frame
            if 'CDS_absolute_end' in exon:
                exon['CDS_frame'] = frame
                cumulative_transcript_length += abs(exon['CDS_absolute_end'] - exon['CDS_absolute_start']) + 1
            if 'stop_codon_absolute_end' in exon:
                exon['stop_codon_frame'] = cumulative_stop_codon_length
                cumulative_stop_codon_length += abs(exon['stop_codon_absolute_end'] - exon['stop_codon_absolute_start']) + 1

    # import pdb; pdb.set_trace()
    # Clean up the data structure and write the json file
    del gene['factorizations']
    with open(output_file, mode='w', encoding='utf-8') as fd:
        fd.write(json.dumps(gene, sort_keys=True, indent=4))


def exec_system_command(command, error_comment, logfile, cmd_label,
                        output_file=""):
    logging.debug(str(time.localtime()))
    logging.debug(command)

    try:
        retcode = subprocess.call(command + " 2>> " + logfile, shell=True)
        if retcode != 0:
            print(error_comment, retcode, file=sys.stderr)
            raise PIntronError(error_comment)
        if os.path.exists("gmon.out"):
            try:
                os.rename("gmon.out", cmd_label+".gmon.out")
            except:
                pass
    except OSError as e:
        print("Execution failed:", e, file=sys.stderr)
        raise PIntronError


def check_executables(bindir, exes):
    """Check if the executables are in the path or in the specified directory.
    """

    full_exes = {}
    if bindir:
        if bindir[0] == '~':
            bindir = os.environ["HOME"] + bindir[1:]
        paths = [bindir] + os.environ["PATH"].split(os.pathsep)
    else:
        paths = os.environ["PATH"].split(os.pathsep)
    for exe in exes:
        full_exes[exe] = None
        for path in paths:
            if os.access(os.path.join(path, exe), os.X_OK):
                real_path = os.path.realpath(os.path.abspath(os.path.join(path, exe)))
                md5hex = md5Checksum(real_path)
                logging.debug("Using program '{}' in dir '{}' (md5: {})".format(exe, real_path, md5hex))
                full_exes[exe] = real_path
                break
        if full_exes[exe] == None:
            raise PIntronIOError(exe, "Could not find program '{}'!\n"
                                 "Search path: {}".format(exe,
                                                          ":".join(paths)))
    return full_exes


def pintron_pipeline(options):
    """Executes the whole pipeline, using the input options.
    """

    logging.info("PIntron%s", pintron_version)
    logging.info("Copyright (C) 2010,2011  Paola Bonizzoni, Gianluca Della Vedova, Yuri Pirola, Raffaella Rizzi.")
    logging.info("This program is distributed under the terms of the GNU Affero General Public License (AGPL), either version 3 of the License, or (at your option) any later version.")
    logging.info("This program comes with ABSOLUTELY NO WARRANTY. See the GNU Affero General Public License for more details.")
    logging.info("This is free software, and you are welcome to redistribute it under the conditions specified by the license.")

    logging.info("Running: " + " ".join(sys.argv))

    # Check and copy input data
    logging.info("STEP  1:  Checking executables and preparing input data...")

    logging.debug("Using main program 'pintron' in dir '{}' (md5: {})".format(os.path.realpath(os.path.abspath(sys.argv[0])),
                                                                              md5Checksum(sys.argv[0])))
    exes = check_executables(options.bindir, ["est-fact",
                                             "min-factorization",
                                             "intron-agreement",
                                             "compact-compositions",
                                             "maximal-transcripts",
                                             "cds-annotation"
                                             ])

    if not os.path.isfile(options.genome_filename) or not os.access(options.genome_filename, os.R_OK):
        raise PIntronIOError(options.genome_filename,
                             'Could not read file "' + options.genome_filename + '"!')
    if not os.path.isfile(options.EST_filename) or not os.access(options.EST_filename, os.R_OK):
        raise PIntronIOError(options.EST_filename,
                             'Could not read file "' + options.EST_filename + '"!')
    if (os.access('genomic.txt', os.F_OK) and
         not os.path.samefile('genomic.txt', options.genome_filename) and
         not os.access('genomic.txt', os.W_OK) ):
        raise PIntronIOError('genomic.txt',
                             'Could not write file "genomic.txt"!')
    if (os.access('ests.txt', os.F_OK) and
         not os.path.samefile('ests.txt', options.EST_filename) and
         not os.access('ests.txt', os.W_OK) ):
        raise PIntronIOError('ests.txt',
                             'Could not write file "ests.txt"!')

    if os.path.isfile('genomic.txt') and os.path.samefile('genomic.txt', options.genome_filename):
        logging.debug('Files "%s" and "genomic.txt" refer to the same file: skip copy.',
                      options.genome_filename)
    else:
        exec_system_command(
            command="cp " + options.genome_filename + " genomic.txt ",
            error_comment="Could not prepare genomic input file",
            logfile=options.plogfile,
            cmd_label='cmd-1a-copy-genomic',
            output_file='raw-multifasta-out.txt')

    if os.path.isfile('ests.txt') and os.path.samefile('ests.txt', options.EST_filename):
        logging.debug('Files "%s" and "ests.txt" refer to the same file: skip copy.',
                      options.EST_filename)
    else:
        exec_system_command(
            command="cp " + options.EST_filename + " ests.txt ",
            error_comment="Could not prepare ESTs input file",
            logfile=options.plogfile,
            cmd_label='cmd-1b-copy-ests',
            output_file='raw-multifasta-out.txt')

    # Compute factorizations
    logging.info("STEP  2:  Pre-aligning transcript data...")

    exec_system_command(
        command="ulimit -t " + str(options.max_factorization_time * 60) + " && ulimit -v " +
        str(options.max_factorization_memory * 1024) + " && " + exes["est-fact"],
        error_comment="Could not compute the factorizations",
        logfile=options.plogfile,
        cmd_label='cmd-2-est-fact',
        output_file='raw-multifasta-out.txt')

    # Min factorization agreement
    logging.info("STEP  3:  Computing a raw consensus gene structure...")

    exec_system_command(
        command="ulimit -t " + str(options.max_exon_agreement_time * 60) + " && " +
        exes["min-factorization"] + " < raw-multifasta-out.txt >out-agree.txt",
        error_comment="Could not minimize the factorizations",
        logfile=options.plogfile,
        cmd_label='cmd-3-min-factorization',
        output_file='out-agree.txt')

    # Intron prediction
    logging.info("STEP  4:  Predicting introns...")

    exec_system_command(
        command="ulimit -t " + str(options.max_intron_agreement_time * 60) + " && " +
        exes["intron-agreement"],
        error_comment="Could not compute the factorizations",
        logfile=options.plogfile,
        cmd_label='cmd-4-intron-agreement',
        output_file='out-after-intron-agree.txt')

    # The computation of the full-length isoforms should not be avoided
    # if options.step1:
    #     sys.exit(0)

    # Transform compositions into exons
    logging.info("STEP  5:  Computing the final transcript alignments...")

    exec_system_command(
        command=exes["compact-compositions"] + " < out-after-intron-agree.txt > build-ests.txt",
        error_comment="Could not transform factorizations into exons",
        logfile=options.plogfile,
        cmd_label='cmd-5-compact-compositions',
        output_file='build-ests.txt')

    # Compute maximal transcripts
    logging.info("STEP  6:  Computing the final full-length isoforms...")

    exec_system_command(
        command=exes["maximal-transcripts"] + " < build-ests.txt",
        error_comment="Could not compute maximal transcripts",
        logfile=options.plogfile,
        cmd_label='cmd-6a-maximal-transcripts',
        output_file='CCDS_transcripts.txt')
    exec_system_command(
        command="cp -f TRANSCRIPTS1_1.txt isoforms.txt",
        error_comment="Could not link isoforms",
        logfile=options.plogfile,
        cmd_label='cmd-6b-copy-maximal-transcripts',
        output_file='CCDS_transcripts.txt')

    # Annotate CDS
    logging.info("STEP  7:  Annotating CDS...")

    exec_system_command(
        command=exes["cds-annotation"] + " ./ ./ " + options.gene + " " + options.organism,
        error_comment="Could not annotate the CDSs",
        logfile=options.plogfile,
        cmd_label='cmd-7-cds-annotation',
        output_file='CCDS_transcripts.txt')

    # TODO: Transcripts browser
    # Output the desired file
    logging.info("STEP  8:  Saving outputs...")

    json_output = compute_json(ccds_file="CCDS_transcripts.txt",
                             variant_file="VariantGTF.txt",
                             output_file=options.output_filename,
                             pas_tolerance=options.pas_tolerance,
                             genomic_seq=options.genome_filename)

    if options.gtf_filename:
        json2gtf(options.output_filename, options.gtf_filename, options.gene,
                 not options.only_cds_annot)

    # Clean mess
    logging.info("STEP 10:  Finalizing...")

    if options.compress:
        exec_system_command("gzip -q9 " + " ".join([options.output_filename,
                                                    options.plogfile,
                                                    options.glogfile]),
                            error_comment="Could not compress final files",
                            logfile="/dev/null",
                            cmd_label='cmd-10-compress',
                            output_file=options.output_filename + '.gz')

    if not options.no_clean:
        tempfiles = ("TEMP_COMPOSITION_TRANS1_1.txt", "TEMP_COMPOSITION_TRANS1_2.txt",
                   "TEMP_COMPOSITION_TRANS1_3.txt", "TEMP_COMPOSITION_TRANS1_4.txt",
                   "TRANSCRIPTS1_1.txt", "TRANSCRIPTS1_2.txt", "TRANSCRIPTS1_3.txt", "TRANSCRIPTS1_4.txt",
                   "VariantGTF.txt", "build-ests.txt", "CCDS_transcripts.txt", "config-dump.ini",
                   "genomic-exonforCCDS.txt", "info-pid-*.log", "isoforms.txt",
                   "meg-edges.txt", "megs.txt", "out-after-intron-agree.txt", "out-agree.txt", "out-fatt.txt",
                   "predicted-introns.txt", "processed-ests.txt", "processed-megs-info.txt",
                   "processed-megs.txt", "raw-multifasta-out.txt", "time-limits")
        subprocess.call("rm -f " + " ".join(tempfiles), shell=True)


def prepare_loggers(options):
    """Prepare loggers.

    Save DEBUG and higher messages to options.glogfile, and INFO and higher messages to stdout
    Code adapted from
    http://docs.python.org/py3k/library/logging.html?highlight=logging#logging-to-multiple-destinations
    """
    logging.basicConfig(filename=options.glogfile,
                        filemode='w',
                        format='%(levelname)s:%(name)s:%(asctime)s%(msecs)d:%(message)s',
                        datefmt='%Y%m%d-%H%M%S',
                        level=logging.DEBUG)
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter('[%(levelname)-8s] %(asctime)s - %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)


if __name__ == '__main__':

    try:
        options = parse_command_line()
## Program version
        pintron_version = '_____%PINTRON_VERSION%_____'
        if (pintron_version[0] == '_' and
            pintron_version[1:] == '____%PINTRON_VERSION%_____'):
            options.version = ''
        else:
            options.version = pintron_version
        prepare_loggers(options)
        pintron_pipeline(options)
    except PIntronError as err:
        logging.exception("*** Fatal error caught during the execution of the pipeline! ***\n"
                          "%s", err)

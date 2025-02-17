# -*- coding: utf-8 -*-
"""KOBART_YTH.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/gist/omkrth/4ca007fcb47c19712e3f8589f19f4dd2/kobart_yth.ipynb
"""

#kobart에 있는 소스 가져오기
pip install git+https://github.com/SKT-AI/KoBART#egg=kobart

!pip install git+https://github.com/PyTorchLightning/pytorch-lightning fsspec --no-deps --target=$nb_path

"""# **Get_Binary**"""

import os
import gdown

if os.path.exists('kobart_summary/config.json') and os.path.exists('kobart_summary/pytorch_model.bin') :
    print("== Data existed.==")
    pass
else:
    os.system("rm -rf kobary_summary")
    os.system("mkdir kobart_summary")
    url = "https://drive.google.com/uc?id=1H13loH6dS_2c2Z21kaBtgz42QsjkdAwO"
    output = './kobart_summary/config.json'
    print("Download config.json")
    gdown.download(url, output, quiet=False)

    url = "https://drive.google.com/uc?id=1D7BAXK_0faWW39c0ptE3FtROsVRbTNwI"
    output = './kobart_summary/pytorch_model.bin'
    print("Download pytorch_model.bin")
    gdown.download(url, output, quiet=False)

"""# **Dataset.py**"""

import os
import glob
import torch
import ast
import numpy as np
import pandas as pd
from tqdm import tqdm, trange
from torch.utils.data import Dataset, DataLoader, IterableDataset

class KoBARTSummaryDataset(Dataset):
    def __init__(self, file, tok, max_len, pad_index = None, ignore_index=-100):
        super().__init__()
        self.tok = tok
        self.max_len = max_len
        self.docs = pd.read_csv(file, sep='\t')
        self.len = self.docs.shape[0]
        if pad_index is None:
            self.pad_index = self.tok.pad_token_id
        else:
            self.pad_index = pad_index
        self.ignore_index = ignore_index

    def add_padding_data(self, inputs):
        if len(inputs) < self.max_len:
            pad = np.array([self.pad_index] *(self.max_len - len(inputs)))
            inputs = np.concatenate([inputs, pad])
        else:
            inputs = inputs[:self.max_len]

        return inputs

    def add_ignored_data(self, inputs):
        if len(inputs) < self.max_len:
            pad = np.array([self.ignore_index] *(self.max_len - len(inputs)))
            inputs = np.concatenate([inputs, pad])
        else:
            inputs = inputs[:self.max_len]

        return inputs
    
    def __getitem__(self, idx):
        instance = self.docs.iloc[idx]
        input_ids = self.tok.encode(instance['news'])
        input_ids = self.add_padding_data(input_ids)

        label_ids = self.tok.encode(instance['summary'])
        label_ids.append(self.tok.eos_token_id)
        dec_input_ids = [self.tok.eos_token_id]
        dec_input_ids += label_ids[:-1]
        dec_input_ids = self.add_padding_data(dec_input_ids)
        label_ids = self.add_ignored_data(label_ids)

#         return (torch.tensor(input_ids),
#                 torch.tensor(dec_input_ids),
#                 torch.tensor(label_ids))
        return {'input_ids': np.array(input_ids, dtype=np.int_),
                'decoder_input_ids': np.array(dec_input_ids, dtype=np.int_),
                'labels': np.array(label_ids, dtype=np.int_)}
    
    def __len__(self):
        return self.len

"""# **Rough.py**"""

pip install konlpy

import os
import re
import platform
import itertools
import collections
import pkg_resources  # pip install py-rouge
from io import open
from konlpy.tag import Mecab




class Rouge:
    DEFAULT_METRICS = {"rouge-n"}
    DEFAULT_N = 1
    STATS = ["f", "p", "r"]
    AVAILABLE_METRICS = {"rouge-n", "rouge-l", "rouge-w"}
    AVAILABLE_LENGTH_LIMIT_TYPES = {"words", "bytes"}
    REMOVE_CHAR_PATTERN = re.compile("[^A-Za-z0-9가-힣]")


    def __init__(
        self,
        metrics=None,
        max_n=None,
        limit_length=True,
        length_limit=1000,
        length_limit_type="words",
        apply_avg=True,
        apply_best=False,
        use_tokenizer=True,
        alpha=0.5,
        weight_factor=1.0,
    ):
        self.metrics = metrics[:] if metrics is not None else Rouge.DEFAULT_METRICS
        for m in self.metrics:
            if m not in Rouge.AVAILABLE_METRICS:
                raise ValueError("Unknown metric '{}'".format(m))


        self.max_n = max_n if "rouge-n" in self.metrics else None
        # Add all rouge-n metrics
        if self.max_n is not None:
            index_rouge_n = self.metrics.index("rouge-n")
            del self.metrics[index_rouge_n]
            self.metrics += ["rouge-{}".format(n) for n in range(1, self.max_n + 1)]
        self.metrics = set(self.metrics)


        self.limit_length = limit_length
        if self.limit_length:
            if length_limit_type not in Rouge.AVAILABLE_LENGTH_LIMIT_TYPES:
                raise ValueError("Unknown length_limit_type '{}'".format(length_limit_type))


        self.length_limit = length_limit
        if self.length_limit == 0:
            self.limit_length = False
        self.length_limit_type = length_limit_type


        self.use_tokenizer = use_tokenizer
        if use_tokenizer:
            self.tokenizer = Mecab()


        self.apply_avg = apply_avg
        self.apply_best = apply_best
        self.alpha = alpha
        self.weight_factor = weight_factor
        if self.weight_factor <= 0:
            raise ValueError("ROUGE-W weight factor must greater than 0.")


    def tokenize_text(self, text):
        if self.use_tokenizer:
            return self.tokenizer.morphs(text)
        else:
            return text


    @staticmethod
    def split_into_sentences(text):
        return text.split("\n")


    @staticmethod
    def _get_ngrams(n, text):
        ngram_set = collections.defaultdict(int)
        max_index_ngram_start = len(text) - n
        for i in range(max_index_ngram_start + 1):
            ngram_set[tuple(text[i : i + n])] += 1
        return ngram_set


    @staticmethod
    def _split_into_words(sentences):
        return list(itertools.chain(*[_.split() for _ in sentences]))


    @staticmethod
    def _get_word_ngrams_and_length(n, sentences):
        assert len(sentences) > 0
        assert n > 0


        tokens = Rouge._split_into_words(sentences)
        return Rouge._get_ngrams(n, tokens), tokens, len(tokens) - (n - 1)


    @staticmethod
    def _get_unigrams(sentences):
        assert len(sentences) > 0


        tokens = Rouge._split_into_words(sentences)
        unigram_set = collections.defaultdict(int)
        for token in tokens:
            unigram_set[token] += 1
        return unigram_set, len(tokens)


    @staticmethod
    def _compute_p_r_f_score(
        evaluated_count,
        reference_count,
        overlapping_count,
        alpha=0.5,
        weight_factor=1.0,
    ):
        precision = 0.0 if evaluated_count == 0 else overlapping_count / float(evaluated_count)
        if weight_factor != 1.0:
            precision = precision ** (1.0 / weight_factor)
        recall = 0.0 if reference_count == 0 else overlapping_count / float(reference_count)
        if weight_factor != 1.0:
            recall = recall ** (1.0 / weight_factor)
        f1_score = Rouge._compute_f_score(precision, recall, alpha)
        return {"f": f1_score, "p": precision, "r": recall}


    @staticmethod
    def _compute_f_score(precision, recall, alpha=0.5):
        return (
            0.0
            if (recall == 0.0 or precision == 0.0)
            else precision * recall / ((1 - alpha) * precision + alpha * recall)
        )


    @staticmethod
    def _compute_ngrams(evaluated_sentences, reference_sentences, n):
        if len(evaluated_sentences) <= 0 or len(reference_sentences) <= 0:
            raise ValueError("Collections must contain at least 1 sentence.")


        evaluated_ngrams, _, evaluated_count = Rouge._get_word_ngrams_and_length(
            n, evaluated_sentences
        )
        reference_ngrams, _, reference_count = Rouge._get_word_ngrams_and_length(
            n, reference_sentences
        )


        # Gets the overlapping ngrams between evaluated and reference
        overlapping_ngrams = set(evaluated_ngrams.keys()).intersection(set(reference_ngrams.keys()))
        overlapping_count = 0
        for ngram in overlapping_ngrams:
            overlapping_count += min(evaluated_ngrams[ngram], reference_ngrams[ngram])


        return evaluated_count, reference_count, overlapping_count


    @staticmethod
    def _compute_ngrams_lcs(evaluated_sentences, reference_sentences, weight_factor=1.0):
        def _lcs(x, y):
            m = len(x)
            n = len(y)
            vals = collections.defaultdict(int)
            dirs = collections.defaultdict(int)


            for i in range(1, m + 1):
                for j in range(1, n + 1):
                    if x[i - 1] == y[j - 1]:
                        vals[i, j] = vals[i - 1, j - 1] + 1
                        dirs[i, j] = "|"
                    elif vals[i - 1, j] >= vals[i, j - 1]:
                        vals[i, j] = vals[i - 1, j]
                        dirs[i, j] = "^"
                    else:
                        vals[i, j] = vals[i, j - 1]
                        dirs[i, j] = "<"


            return vals, dirs


        def _wlcs(x, y, weight_factor):
            m = len(x)
            n = len(y)
            vals = collections.defaultdict(float)
            dirs = collections.defaultdict(int)
            lengths = collections.defaultdict(int)


            for i in range(1, m + 1):
                for j in range(1, n + 1):
                    if x[i - 1] == y[j - 1]:
                        length_tmp = lengths[i - 1, j - 1]
                        vals[i, j] = (
                            vals[i - 1, j - 1]
                            + (length_tmp + 1) ** weight_factor
                            - length_tmp ** weight_factor
                        )
                        dirs[i, j] = "|"
                        lengths[i, j] = length_tmp + 1
                    elif vals[i - 1, j] >= vals[i, j - 1]:
                        vals[i, j] = vals[i - 1, j]
                        dirs[i, j] = "^"
                        lengths[i, j] = 0
                    else:
                        vals[i, j] = vals[i, j - 1]
                        dirs[i, j] = "<"
                        lengths[i, j] = 0


            return vals, dirs


        def _mark_lcs(mask, dirs, m, n):
            while m != 0 and n != 0:
                if dirs[m, n] == "|":
                    m -= 1
                    n -= 1
                    mask[m] = 1
                elif dirs[m, n] == "^":
                    m -= 1
                elif dirs[m, n] == "<":
                    n -= 1
                else:
                    raise UnboundLocalError("Illegal move")


            return mask


        if len(evaluated_sentences) <= 0 or len(reference_sentences) <= 0:
            raise ValueError("Collections must contain at least 1 sentence.")


        evaluated_unigrams_dict, evaluated_count = Rouge._get_unigrams(evaluated_sentences)
        reference_unigrams_dict, reference_count = Rouge._get_unigrams(reference_sentences)


        # Has to use weight factor for WLCS
        use_WLCS = weight_factor != 1.0
        if use_WLCS:
            evaluated_count = evaluated_count ** weight_factor
            reference_count = 0


        overlapping_count = 0.0
        for reference_sentence in reference_sentences:
            reference_sentence_tokens = reference_sentence.split()
            if use_WLCS:
                reference_count += len(reference_sentence_tokens) ** weight_factor
            hit_mask = [0 for _ in range(len(reference_sentence_tokens))]


            for evaluated_sentence in evaluated_sentences:
                evaluated_sentence_tokens = evaluated_sentence.split()


                if use_WLCS:
                    _, lcs_dirs = _wlcs(
                        reference_sentence_tokens,
                        evaluated_sentence_tokens,
                        weight_factor,
                    )
                else:
                    _, lcs_dirs = _lcs(reference_sentence_tokens, evaluated_sentence_tokens)
                _mark_lcs(
                    hit_mask,
                    lcs_dirs,
                    len(reference_sentence_tokens),
                    len(evaluated_sentence_tokens),
                )


            overlapping_count_length = 0
            for ref_token_id, val in enumerate(hit_mask):
                if val == 1:
                    token = reference_sentence_tokens[ref_token_id]
                    if evaluated_unigrams_dict[token] > 0 and reference_unigrams_dict[token] > 0:
                        evaluated_unigrams_dict[token] -= 1
                        reference_unigrams_dict[ref_token_id] -= 1


                        if use_WLCS:
                            overlapping_count_length += 1
                            if (
                                ref_token_id + 1 < len(hit_mask) and hit_mask[ref_token_id + 1] == 0
                            ) or ref_token_id + 1 == len(hit_mask):
                                overlapping_count += overlapping_count_length ** weight_factor
                                overlapping_count_length = 0
                        else:
                            overlapping_count += 1


        if use_WLCS:
            reference_count = reference_count ** weight_factor


        return evaluated_count, reference_count, overlapping_count


    def get_scores(self, hypothesis, references):
        if isinstance(hypothesis, str):
            hypothesis, references = [hypothesis], [references]


        if type(hypothesis) != type(references):
            raise ValueError("'hyps' and 'refs' are not of the same type")


        if len(hypothesis) != len(references):
            raise ValueError("'hyps' and 'refs' do not have the same length")
        scores = {}
        has_rouge_n_metric = (
            len([metric for metric in self.metrics if metric.split("-")[-1].isdigit()]) > 0
        )
        if has_rouge_n_metric:
            scores.update(self._get_scores_rouge_n(hypothesis, references))
            # scores = {**scores, **self._get_scores_rouge_n(hypothesis, references)}


        has_rouge_l_metric = (
            len([metric for metric in self.metrics if metric.split("-")[-1].lower() == "l"]) > 0
        )
        if has_rouge_l_metric:
            scores.update(self._get_scores_rouge_l_or_w(hypothesis, references, False))
            # scores = {**scores, **self._get_scores_rouge_l_or_w(hypothesis, references, False)}


        has_rouge_w_metric = (
            len([metric for metric in self.metrics if metric.split("-")[-1].lower() == "w"]) > 0
        )
        if has_rouge_w_metric:
            scores.update(self._get_scores_rouge_l_or_w(hypothesis, references, True))
            # scores = {**scores, **self._get_scores_rouge_l_or_w(hypothesis, references, True)}


        return scores


    def _get_scores_rouge_n(self, all_hypothesis, all_references):
        metrics = [metric for metric in self.metrics if metric.split("-")[-1].isdigit()]


        if self.apply_avg or self.apply_best:
            scores = {metric: {stat: 0.0 for stat in Rouge.STATS} for metric in metrics}
        else:
            scores = {
                metric: [{stat: [] for stat in Rouge.STATS} for _ in range(len(all_hypothesis))]
                for metric in metrics
            }


        for sample_id, (hypothesis, references) in enumerate(zip(all_hypothesis, all_references)):
            assert isinstance(hypothesis, str)
            has_multiple_references = False
            if isinstance(references, list):
                has_multiple_references = len(references) > 1
                if not has_multiple_references:
                    references = references[0]


            # Prepare hypothesis and reference(s)
            hypothesis = self._preprocess_summary_as_a_whole(hypothesis)
            references = (
                [self._preprocess_summary_as_a_whole(reference) for reference in references]
                if has_multiple_references
                else [self._preprocess_summary_as_a_whole(references)]
            )


            # Compute scores
            for metric in metrics:
                suffix = metric.split("-")[-1]
                n = int(suffix)


                # Aggregate
                if self.apply_avg:
                    # average model
                    total_hypothesis_ngrams_count = 0
                    total_reference_ngrams_count = 0
                    total_ngrams_overlapping_count = 0


                    for reference in references:
                        (
                            hypothesis_count,
                            reference_count,
                            overlapping_ngrams,
                        ) = Rouge._compute_ngrams(hypothesis, reference, n)
                        total_hypothesis_ngrams_count += hypothesis_count
                        total_reference_ngrams_count += reference_count
                        total_ngrams_overlapping_count += overlapping_ngrams


                    score = Rouge._compute_p_r_f_score(
                        total_hypothesis_ngrams_count,
                        total_reference_ngrams_count,
                        total_ngrams_overlapping_count,
                        self.alpha,
                    )


                    for stat in Rouge.STATS:
                        scores[metric][stat] += score[stat]
                else:
                    # Best model
                    if self.apply_best:
                        best_current_score = None
                        for reference in references:
                            (
                                hypothesis_count,
                                reference_count,
                                overlapping_ngrams,
                            ) = Rouge._compute_ngrams(hypothesis, reference, n)
                            score = Rouge._compute_p_r_f_score(
                                hypothesis_count,
                                reference_count,
                                overlapping_ngrams,
                                self.alpha,
                            )
                            if best_current_score is None or score["r"] > best_current_score["r"]:
                                best_current_score = score


                        for stat in Rouge.STATS:
                            scores[metric][stat] += best_current_score[stat]
                    # Keep all
                    else:
                        for reference in references:
                            (
                                hypothesis_count,
                                reference_count,
                                overlapping_ngrams,
                            ) = Rouge._compute_ngrams(hypothesis, reference, n)
                            score = Rouge._compute_p_r_f_score(
                                hypothesis_count,
                                reference_count,
                                overlapping_ngrams,
                                self.alpha,
                            )
                            for stat in Rouge.STATS:
                                scores[metric][sample_id][stat].append(score[stat])


        # Compute final score with the average or the the max
        if (self.apply_avg or self.apply_best) and len(all_hypothesis) > 1:
            for metric in metrics:
                for stat in Rouge.STATS:
                    scores[metric][stat] /= len(all_hypothesis)


        return scores


    def _get_scores_rouge_l_or_w(self, all_hypothesis, all_references, use_w=False):
        metric = "rouge-w" if use_w else "rouge-l"
        if self.apply_avg or self.apply_best:
            scores = {metric: {stat: 0.0 for stat in Rouge.STATS}}
        else:
            scores = {
                metric: [{stat: [] for stat in Rouge.STATS} for _ in range(len(all_hypothesis))]
            }


        for sample_id, (hypothesis_sentences, references_sentences) in enumerate(
            zip(all_hypothesis, all_references)
        ):
            assert isinstance(hypothesis_sentences, str)
            has_multiple_references = False
            if isinstance(references_sentences, list):
                has_multiple_references = len(references_sentences) > 1
                if not has_multiple_references:
                    references_sentences = references_sentences[0]


            # Prepare hypothesis and reference(s)
            hypothesis_sentences = self._preprocess_summary_per_sentence(hypothesis_sentences)
            references_sentences = (
                [
                    self._preprocess_summary_per_sentence(reference)
                    for reference in references_sentences
                ]
                if has_multiple_references
                else [self._preprocess_summary_per_sentence(references_sentences)]
            )


            # Compute scores
            # Aggregate
            if self.apply_avg:
                # average model
                total_hypothesis_ngrams_count = 0
                total_reference_ngrams_count = 0
                total_ngrams_overlapping_count = 0


                for reference_sentences in references_sentences:
                    (
                        hypothesis_count,
                        reference_count,
                        overlapping_ngrams,
                    ) = Rouge._compute_ngrams_lcs(
                        hypothesis_sentences,
                        reference_sentences,
                        self.weight_factor if use_w else 1.0,
                    )
                    total_hypothesis_ngrams_count += hypothesis_count
                    total_reference_ngrams_count += reference_count
                    total_ngrams_overlapping_count += overlapping_ngrams


                score = Rouge._compute_p_r_f_score(
                    total_hypothesis_ngrams_count,
                    total_reference_ngrams_count,
                    total_ngrams_overlapping_count,
                    self.alpha,
                    self.weight_factor if use_w else 1.0,
                )
                for stat in Rouge.STATS:
                    scores[metric][stat] += score[stat]
            else:
                # Best model
                if self.apply_best:
                    best_current_score = None
                    best_current_score_wlcs = None
                    for reference_sentences in references_sentences:
                        (
                            hypothesis_count,
                            reference_count,
                            overlapping_ngrams,
                        ) = Rouge._compute_ngrams_lcs(
                            hypothesis_sentences,
                            reference_sentences,
                            self.weight_factor if use_w else 1.0,
                        )
                        score = Rouge._compute_p_r_f_score(
                            total_hypothesis_ngrams_count,
                            total_reference_ngrams_count,
                            total_ngrams_overlapping_count,
                            self.alpha,
                            self.weight_factor if use_w else 1.0,
                        )


                        if use_w:
                            reference_count_for_score = reference_count ** (
                                1.0 / self.weight_factor
                            )
                            overlapping_ngrams_for_score = overlapping_ngrams
                            score_wlcs = (
                                overlapping_ngrams_for_score / reference_count_for_score
                            ) ** (1.0 / self.weight_factor)


                            if (
                                best_current_score_wlcs is None
                                or score_wlcs > best_current_score_wlcs
                            ):
                                best_current_score = score
                                best_current_score_wlcs = score_wlcs
                        else:
                            if best_current_score is None or score["r"] > best_current_score["r"]:
                                best_current_score = score


                    for stat in Rouge.STATS:
                        scores[metric][stat] += best_current_score[stat]
                # Keep all
                else:
                    for reference_sentences in references_sentences:
                        (
                            hypothesis_count,
                            reference_count,
                            overlapping_ngrams,
                        ) = Rouge._compute_ngrams_lcs(
                            hypothesis_sentences,
                            reference_sentences,
                            self.weight_factor if use_w else 1.0,
                        )
                        score = Rouge._compute_p_r_f_score(
                            hypothesis_count,
                            reference_count,
                            overlapping_ngrams,
                            self.alpha,
                            self.weight_factor,
                        )


                        for stat in Rouge.STATS:
                            scores[metric][sample_id][stat].append(score[stat])


        # Compute final score with the average or the the max
        if (self.apply_avg or self.apply_best) and len(all_hypothesis) > 1:
            for stat in Rouge.STATS:
                scores[metric][stat] /= len(all_hypothesis)


        return scores


    def _preprocess_summary_as_a_whole(self, summary):
        sentences = Rouge.split_into_sentences(summary)


        # Truncate
        if self.limit_length:
            # By words
            if self.length_limit_type == "words":
                summary = " ".join(sentences)
                all_tokens = summary.split()  # Counting as in the perls script
                summary = " ".join(all_tokens[: self.length_limit])


            # By bytes
            elif self.length_limit_type == "bytes":
                summary = ""
                current_len = 0
                for sentence in sentences:
                    sentence = sentence.strip()
                    sentence_len = len(sentence)


                    if current_len + sentence_len < self.length_limit:
                        if current_len != 0:
                            summary += " "
                        summary += sentence
                        current_len += sentence_len
                    else:
                        if current_len > 0:
                            summary += " "
                        summary += sentence[: self.length_limit - current_len]
                        break
        else:
            summary = " ".join(sentences)


        summary = Rouge.REMOVE_CHAR_PATTERN.sub(" ", summary.lower()).strip()


        tokens = self.tokenize_text(Rouge.REMOVE_CHAR_PATTERN.sub(" ", summary))
        preprocessed_summary = [" ".join(tokens)]


        return preprocessed_summary


    def _preprocess_summary_per_sentence(self, summary):
        sentences = Rouge.split_into_sentences(summary)


        # Truncate
        if self.limit_length:
            final_sentences = []
            current_len = 0
            # By words
            if self.length_limit_type == "words":
                for sentence in sentences:
                    tokens = sentence.strip().split()
                    tokens_len = len(tokens)
                    if current_len + tokens_len < self.length_limit:
                        sentence = " ".join(tokens)
                        final_sentences.append(sentence)
                        current_len += tokens_len
                    else:
                        sentence = " ".join(tokens[: self.length_limit - current_len])
                        final_sentences.append(sentence)
                        break
            # By bytes
            elif self.length_limit_type == "bytes":
                for sentence in sentences:
                    sentence = sentence.strip()
                    sentence_len = len(sentence)
                    if current_len + sentence_len < self.length_limit:
                        final_sentences.append(sentence)
                        current_len += sentence_len
                    else:
                        sentence = sentence[: self.length_limit - current_len]
                        final_sentences.append(sentence)
                        break
            sentences = final_sentences


        final_sentences = []
        for sentence in sentences:
            sentence = Rouge.REMOVE_CHAR_PATTERN.sub(" ", sentence.lower()).strip()


            tokens = self.tokenize_text(Rouge.REMOVE_CHAR_PATTERN.sub(" ", sentence))


            sentence = " ".join(tokens)


            final_sentences.append(sentence)


        return final_sentences

"""# **Train.py**"""

import torch
torch.__version__

!pip install git+https://github.com/PyTorchLightning/pytorch-lightning

pip install pytorch-lightning

import argparse
import logging
import os
import numpy as np
import pandas as pd
import pytorch_lightning as pl
import torch
from pytorch_lightning import loggers as pl_loggers
from torch.utils.data import DataLoader, Dataset
from dataset import KoBARTSummaryDataset
from transformers import BartForConditionalGeneration, PreTrainedTokenizerFast
from transformers.optimization import AdamW, get_cosine_schedule_with_warmup
from kobart import get_pytorch_kobart_model, get_kobart_tokenizer

parser = argparse.ArgumentParser(description='KoBART Summarization')

parser.add_argument('--checkpoint_path',
                    type=str,
                    help='checkpoint path')

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class ArgsBase():
    @staticmethod
    def add_model_specific_args(parent_parser):
        parser = argparse.ArgumentParser(
            parents=[parent_parser], add_help=False)
        parser.add_argument('--train_file',
                            type=str,
                            default='data/train.tsv',
                            help='train file')

        parser.add_argument('--test_file',
                            type=str,
                            default='data/test.tsv',
                            help='test file')

        parser.add_argument('--batch_size',
                            type=int,
                            default=14,
                            help='')
        parser.add_argument('--max_len',
                            type=int,
                            default=512,
                            help='max seq len')
        return parser

class KobartSummaryModule(pl.LightningDataModule):
    def __init__(self, train_file,
                 test_file, tok,
                 max_len=512,
                 batch_size=8,
                 num_workers=5):
        super().__init__()
        self.batch_size = batch_size
        self.max_len = max_len
        self.train_file_path = train_file
        self.test_file_path = test_file
        if tok is None:
            self.tok = get_kobart_tokenizer()
        else:
            self.tok = tok
        self.num_workers = num_workers

    @staticmethod
    def add_model_specific_args(parent_parser):
        parser = argparse.ArgumentParser(
            parents=[parent_parser], add_help=False)
        parser.add_argument('--num_workers',
                            type=int,
                            default=5,
                            help='num of worker for dataloader')
        return parser

    # OPTIONAL, called for every GPU/machine (assigning state is OK)
    def setup(self, stage):
        # split dataset
        self.train = KoBARTSummaryDataset(self.train_file_path,
                                 self.tok,
                                 self.max_len)
        self.test = KoBARTSummaryDataset(self.test_file_path,
                                self.tok,
                                self.max_len)

    def train_dataloader(self):
        train = DataLoader(self.train,
                           batch_size=self.batch_size,
                           num_workers=self.num_workers, shuffle=True)
        return train

    def val_dataloader(self):
        val = DataLoader(self.test,
                         batch_size=self.batch_size,
                         num_workers=self.num_workers, shuffle=False)
        return val

    def test_dataloader(self):
        test = DataLoader(self.test,
                          batch_size=self.batch_size,
                          num_workers=self.num_workers, shuffle=False)
        return test


class Base(pl.LightningModule):
    def __init__(self, hparams, **kwargs) -> None:
        super(Base, self).__init__()
        self.save_hyperparameters(hparams)

    @staticmethod
    def add_model_specific_args(parent_parser):
        # add model specific args
        parser = argparse.ArgumentParser(
            parents=[parent_parser], add_help=False)

        parser.add_argument('--batch-size',
                            type=int,
                            default=14,
                            help='batch size for training (default: 96)')

        parser.add_argument('--lr',
                            type=float,
                            default=3e-5,
                            help='The initial learning rate')

        parser.add_argument('--warmup_ratio',
                            type=float,
                            default=0.1,
                            help='warmup ratio')

        parser.add_argument('--model_path',
                            type=str,
                            default=None,
                            help='kobart model path')
        return parser

    def configure_optimizers(self):
        # Prepare optimizer
        param_optimizer = list(self.model.named_parameters())
        no_decay = ['bias', 'LayerNorm.bias', 'LayerNorm.weight']
        optimizer_grouped_parameters = [
            {'params': [p for n, p in param_optimizer if not any(
                nd in n for nd in no_decay)], 'weight_decay': 0.01},
            {'params': [p for n, p in param_optimizer if any(
                nd in n for nd in no_decay)], 'weight_decay': 0.0}
        ]
        optimizer = AdamW(optimizer_grouped_parameters,
                          lr=self.hparams.lr, correct_bias=False)
        num_workers = self.hparams.num_workers
        data_len = len(self.train_dataloader().dataset)
        logging.info(f'number of workers {num_workers}, data length {data_len}')
        num_train_steps = int(data_len / (self.hparams.batch_size * num_workers) * self.hparams.max_epochs)
        logging.info(f'num_train_steps : {num_train_steps}')
        num_warmup_steps = int(num_train_steps * self.hparams.warmup_ratio)
        logging.info(f'num_warmup_steps : {num_warmup_steps}')
        scheduler = get_cosine_schedule_with_warmup(
            optimizer,
            num_warmup_steps=num_warmup_steps, num_training_steps=num_train_steps)
        lr_scheduler = {'scheduler': scheduler, 
                        'monitor': 'loss', 'interval': 'step',
                        'frequency': 1}
        return [optimizer], [lr_scheduler]


class KoBARTConditionalGeneration(Base):
    def __init__(self, hparams, **kwargs):
        super(KoBARTConditionalGeneration, self).__init__(hparams, **kwargs)
        self.model = BartForConditionalGeneration.from_pretrained(get_pytorch_kobart_model())
        self.model.train()
        self.bos_token = '<s>'
        self.eos_token = '</s>'
        self.pad_token_id = 0
        self.tokenizer = get_kobart_tokenizer()

    def forward(self, inputs):

        attention_mask = inputs['input_ids'].ne(self.pad_token_id).float()
        decoder_attention_mask = inputs['decoder_input_ids'].ne(self.pad_token_id).float()
        
        return self.model(input_ids=inputs['input_ids'],
                          attention_mask=attention_mask,
                          decoder_input_ids=inputs['decoder_input_ids'],
                          decoder_attention_mask=decoder_attention_mask,
                          labels=inputs['labels'], return_dict=True)


    def training_step(self, batch, batch_idx):
        outs = self(batch)
        loss = outs.loss
        self.log('train_loss', loss, prog_bar=True)
        return loss

    def validation_step(self, batch, batch_idx):
        outs = self(batch)
        loss = outs['loss']
        return (loss)

    def validation_epoch_end(self, outputs):
        losses = []
        for loss in outputs:
            losses.append(loss)
        self.log('val_loss', torch.stack(losses).mean(), prog_bar=True)

if __name__ == '__main__':
    parser = Base.add_model_specific_args(parser)
    parser = ArgsBase.add_model_specific_args(parser)
    parser = KobartSummaryModule.add_model_specific_args(parser)
    parser = pl.Trainer.add_argparse_args(parser)
    args = parser.parse_args()
    logging.info(args)

    model = KoBARTConditionalGeneration(args)

    dm = KobartSummaryModule(args.train_file,
                        args.test_file,
                        None,
                        batch_size=args.batch_size,
                        max_len=args.max_len,
                        num_workers=args.num_workers)
    
    checkpoint_callback = pl.callbacks.ModelCheckpoint(monitor='val_loss',
                                                       dirpath=args.default_root_dir,
                                                       filename='model_chp/{epoch:02d}-{val_loss:.3f}',
                                                       verbose=True,
                                                       save_last=True,
                                                       mode='min',
                                                       save_top_k=-1)
    tb_logger = pl_loggers.TensorBoardLogger(os.path.join(args.default_root_dir, 'tb_logs'))
    lr_logger = pl.callbacks.LearningRateMonitor()
    trainer = pl.Trainer.from_argparse_args(args, logger=tb_logger,
                                            callbacks=[checkpoint_callback, lr_logger])
    trainer.fit(model, dm)


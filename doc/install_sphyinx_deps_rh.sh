#!/bin/sh

pkgs="$pkgs texlive-xetex"
pkgs="$pkgs texlive-amsfonts texlive-amsmath texlive-amsfonts texlive-amscls texlive-anyfontsize"
pkgs="$pkgs texlive-oberdiek texlive-tools texlive-capt-of texlive-cmap texlive-ec"
pkgs="$pkgs texlive-eqparbox texlive-euenc texlive-fancybox texlive-fancyvrb texlive-float"
pkgs="$pkgs texlive-fncychap texlive-mdwtools texlive-framed texlive-luatex85"
pkgs="$pkgs texlive-multirow texlive-needspace texlive-psnfss texlive-parskip"
pkgs="$pkgs texlive-polyglossia texlive-tabulary texlive-threeparttable"
pkgs="$pkgs texlive-titlesec texlive-ucs texlive-upquote texlive-wrapfig"

sudo yum install -y ${pkgs}


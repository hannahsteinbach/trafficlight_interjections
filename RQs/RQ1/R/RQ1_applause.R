# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
##header ##
# R version 4.1.1 (2021-08-10)
# Platform: x86_64-w64-mingw32/x64 (64-bit)

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
## setup  ----
rm(list=ls())

# check whether other packages than base packages are loaded
# if yes, they are detached to avoid
loadedpackages <- names(sessionInfo()$otherPkgs)
if (length(loadedpackages>0)) {
  lapply(paste("package",loadedpackages, sep=":"), detach, character.only = TRUE, unload = TRUE)
}

# define and set working directory
setwd("C:/Users/hanna/OneDrive/Dokumente/Master/4.Semester/Ampel/RQs/RQ1/R")


# check if required folders exist
folders <- c("data","scripts","out")
all(sapply(folders, dir.exists))

# install required packages from CRAN
p_needed <- c("devtools","dplyr","emmeans","MASS", "tidyr")
# package versions used: devtools 2.4.3; dplyr 1.0.7; emmeans 1.7.1-1; MASS 7.3-54
packages <- rownames(installed.packages())
p_to_install <- p_needed[!(p_needed %in% packages)]
if (length(p_to_install) > 0) {
  install.packages(p_to_install)
}

# load packages
lapply(p_needed, require, character.only = TRUE)

try(ggeffectsversion <- utils::packageDescription("ggeffects")$Version)
install_github("imrem/ggeffects", upgrade="never")
require(ggeffects)

rm(list=setdiff(ls(), "ggeffectsversion"))


scorebymonth <- read.csv("data/normalized_interjectionscore.csv")
applausebymonth <- read.csv("data/applause_month_encoded.csv")

library(dplyr)

# Merge by month
combined_monthly <- merge(scorebymonth, applausebymonth, by = "Month", all = TRUE)

combined_monthly$speech_tokens <- applausebymonth$speech_tokens[
  match(combined_monthly$Month, applausebymonth$Month)
]

combined_monthly <- combined_monthly %>%
  mutate(
    InterjectionScore = replace_na(InterjectionScore_norm, 0),
    applausescore = replace_na(applausescore, 0)
  )

combined_monthly$applause_rate <- combined_monthly$applausescore / combined_monthly$speech_tokens*10000
combined_monthly$interjection_rate <- combined_monthly$InterjectionScore 

# Pearson
cor(combined_monthly$interjection_rate,
    combined_monthly$applause_rate,
    use = "complete.obs")

# Spearman
cor(combined_monthly$interjection_rate,
    combined_monthly$applause_rate,
    use = "complete.obs",
    method = "spearman")


cor.test(combined_monthly$interjection_rate,
         combined_monthly$applause_rate)


library(ggplot2)

ggplot(combined_monthly, aes(x = combined_monthly$applause_rate, y = combined_monthly$interjection_rate)) +
  geom_point(size = 3, alpha = 0.7) +
  geom_smooth(method = "lm", se = TRUE) +
  labs(
    x = "Applause Score",
    y = "Interjection Score (cooperative – confrontational)",
    title = "Relationship between Interjection Climate and Applause"
  ) +
  theme_minimal()

# Scatterplot with regression line
p <- ggplot(combined_monthly, aes(x = total_interjection, y = total_applause)) +
  geom_point(size = 3, color = "#2c7bb6") +
  geom_smooth(method = "lm", color = "#fdae61", se = TRUE) +
  labs(
    x = "Total Interjection Score (gov-gov, per month)",
    y = "Total Applause (gov-gov, per month)",
    title = "Monthly Total Interjections Scores vs Applause (raw)"
  ) +
  theme_minimal(base_size = 14) +
  annotate(
    "text", x = min(combined_monthly$total_interjection), 
    y = max(combined_monthly$total_applause),
    label = paste0("Pearson r = ", round(cor(combined_monthly$total_interjection, combined_monthly$total_applause), 2),
                   "\nSpearman rho = ", round(cor(combined_monthly$total_interjection, combined_monthly$total_applause, method = "spearman"), 2)),
    hjust = 0, vjust = 1, size = 5
  )
p

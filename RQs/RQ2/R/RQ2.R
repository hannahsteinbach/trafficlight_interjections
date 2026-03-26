# ============================================================
# 1. Load packages
# ============================================================
packages <- c("ggplot2", "dplyr", "emmeans", "lme4", "tidyr")
install.packages(setdiff(packages, installed.packages()[,1]))
lapply(packages, library, character.only = TRUE)


# ============================================================
# 2. Load data
# ============================================================
setwd("C:/Users/hanna/OneDrive/Dokumente/Master/4.Semester/Ampel/RQs/RQ2/R")
library(dplyr)
library(tidyr)

# --------------------------
# Directed
# --------------------------
directed <- read.csv("data/interjectionscorebymonthpartypair.csv")
directed$PartyPair <- factor(directed$PartyPair)

# Make Month a character to avoid as.Date errors
directed$Month <- as.character(directed$Month)

# Fill missing Month × PartyPair combinations with 0
directed <- directed %>%
  complete(PartyPair, Month, fill = list(interjection_rate = 0)) %>%
  arrange(PartyPair, Month)

# Add October 2021 (sessions present but no interjections)
if(!"2021-10" %in% directed$Month){
  new_rows <- expand.grid(
    PartyPair = unique(directed$PartyPair),
    Month = "2021-10",
    interjection_rate = 0
  )
  directed <- bind_rows(directed, new_rows) %>% arrange(PartyPair, Month)
}

# Make SPD->GRUENE the reference
directed$PartyPair <- relevel(directed$PartyPair, ref = "SPD–>GRUENE")

# Convert Month to Date safely
directed$MonthDate <- as.Date(paste0(directed$Month, "-01"), format="%Y-%m-%d")

# --------------------------
# Undirected
# --------------------------
undirected <- read.csv("data/interjectionscorebymonthundirected.csv")
undirected$UndirectedPartyPair <- factor(undirected$UndirectedPartyPair)
undirected$Month <- as.character(undirected$Month)

undirected <- undirected %>%
  complete(UndirectedPartyPair, Month, fill = list(interjection_rate = 0)) %>%
  arrange(UndirectedPartyPair, Month)

# Add October 2021 (sessions present but no interjections)
if(!"2021-10" %in% undirected$Month){
  new_rows <- expand.grid(
    UndirectedPartyPair = unique(undirected$UndirectedPartyPair),
    Month = "2021-10",
    interjection_rate = 0
  )
  undirected <- bind_rows(undirected, new_rows) %>% arrange(UndirectedPartyPair, Month)
}

# Make GRUENE-SPD the reference
undirected$UndirectedPartyPair <- relevel(undirected$UndirectedPartyPair, ref = "GRUENE-SPD")

# Convert Month to Date safely
undirected$MonthDate <- as.Date(paste0(undirected$Month, "-01"), format="%Y-%m-%d")



# ============================================================
# Add Before/After variable (Period)
# ============================================================
cutoff <- as.Date("2024-11-01")
directed$Period <- factor(ifelse(directed$MonthDate < cutoff, "Before", "After"),
                          levels = c("Before", "After"))
undirected$Period <- factor(ifelse(undirected$MonthDate < cutoff, "Before", "After"),
                            levels = c("Before", "After"))

# ============================================================
# Fit Models
# ============================================================

model_directed_interaction <- lm(interjection_rate ~ Period * PartyPair, data = directed)
summary(model_directed_interaction)

# Reference is PartyPair SPD->GRUENE, Period Before 
# PeriodAfter                       -0.43131 0.79241 , SPD->GRUENE change after novembver 2024 is essentially 0, did not change behavior
# stable dyad (PeriodAfter estimated intercept -0.43131 p value 0.79241, not significant)
# other dyads have a signficiant drop in interjection cooperation:
# PeriodAfter:PartyPairFDP–>GRUENE  -7.36615 p value 0.00168 ** 
# PeriodAfter:PartyPairGRUENE–>FDP -18.57123 6.51e-14 ***
# PeriodAfter:PartyPairFDP–>SPD    -10.60578  7.79e-06 ***
# PeriodAfter:PartyPairSPD–>FDP    -12.65746 1.25e-07 ***
# only dyads without decline is the reference dyad (SPD->Gruene) and the other direction 
# (PeriodAfter:PartyPairGRUENE–>SPD   0.02164    2.44723   0.009  0.99295    )
# i.e. very strong overall decline in Interjection Scores after November 2024
# but no signficiant changes in behaviour across dyads BEFORE november 2024


# --- Undirected ---
model_undirected_interaction <- lm(interjection_rate ~ Period * UndirectedPartyPair, data = undirected)
summary(model_undirected_interaction)
# Reference dyad SPD-GRUENE, Period Before 
# PeriodAfter  -0.01405    0.991076, GRUENE-SPD change after november 2024 is essentially 0, did not change behavior
# other dyads have a signficiant drop in interjection cooperation:
# PeriodAfter:UndirectedPartyPairFDP-GRUENE -12.26833    1.77259  -6.921 3.33e-10 ***
# PeriodAfter:UndirectedPartyPairFDP-SPD    -11.63268    1.77259  -6.563 1.89e-09 ***
# both dropped significantly more than GRUENE-SPD
# again, no significant differences in behavior across dyads BEFORE november 2024
# Before the FDP left the government, none of the FDP dyads differed reliably from GRUENE–SPD in their Interjection Scores


## conclusion: After the coalition breakup, FDP–GREEN and FDP–SPD interjections became dramatically less cooperative, on average, compared to the pre-period,
## while SPD-GRUENE Interjection Scores remained stable. Before the breakup, there were no significant differences



# ============================================================
# Plots
# ============================================================
# Directed: trend over time
p <- ggplot(directed, aes(x = MonthDate, y = interjection_rate, color = PartyPair)) +
  geom_point(alpha = 0.6) +
  geom_line(aes(group = PartyPair), alpha = 0.3) +
  geom_smooth(aes(y = interjection_rate), method = "lm", se = TRUE, color = "red") +
  geom_vline(xintercept = cutoff, linetype = "dashed", color = "black") +
  scale_x_date(
    date_breaks = "3 months",
    date_minor_breaks = "1 month",
    date_labels = "%m/%y"
  ) +
  labs(
    x = "Month",
    y = "Interjection Score (per 10k tokens)",
    color = "(Directed) Party Combination\n(Interjector->Speaker)",
    title = "Interjection Scores: Monthly Trend",
    subtitle = "Red line = overall trend, dashed line = Nov 2024 (FDP exit)"
  ) +
  theme_minimal(base_size = 14) +
  theme(
    axis.text.x = element_text(angle = 45, hjust = 1),
    panel.grid.minor = element_line(color = "gray90", linetype = "dotted"),
    panel.grid.major = element_line(color = "gray80")
  )
ggsave("out/directed_monthlytrend.png", plot = p, width = 10, height = 6, dpi = 300)

# undirected
p <- ggplot(undirected, 
            aes(x = MonthDate, 
                y = interjection_rate, 
                color = UndirectedPartyPair)) +
  geom_point(alpha = 0.6) +
  geom_line(aes(group = UndirectedPartyPair), alpha = 0.5) +
  geom_vline(xintercept = cutoff, linetype = "dashed", color = "black") +
  scale_color_manual(
    values = c(
      "GRUENE-SPD" = "#8B3A3A",
      "FDP-GRUENE" = "#9ACD32",
      "FDP-SPD"    = "#FF8C00"
    ),
    labels = c(
      "GRUENE-SPD" = "Greens–SPD",
      "FDP-GRUENE" = "FDP–Greens",
      "FDP-SPD"    = "FDP–SPD"
    )
  ) +
  scale_x_date(date_labels = "%m %Y", date_breaks = "1 month") +
  labs(
    x = "Month",
    y = "Normalized Interjection Score",
    color = "Party Combination",
    title = "Interjection Scores: Monthly Trend",
    subtitle = "Dashed line = Nov 2024 (FDP exit)"
  ) +
  theme_minimal() +
  theme(
    axis.text.x = element_text(angle = 60, hjust = 1, size = 12),
    axis.text.y = element_text(size = 12),
    axis.title.x = element_text(size = 14),
    axis.title.y = element_text(size = 14),
    plot.title = element_text(size = 16, face = "bold"),
    plot.subtitle = element_text(size = 13),
    panel.grid.minor.x = element_blank()
  )

ggsave("out/undirected_monthlytrend.png", plot = p, width = 10, height = 6, dpi = 300)


# --- 1. Load packages ---
install.packages(c("ggplot2", "sjPlot", "dplyr"))
library(ggplot2)
library(zoo)
library(dplyr)
library(sjPlot)

# --- 2. Month-level data (aggregated interjections, +1 for "cooperative", -1 for "confrontational,
# --- normalized by num. of token per month spoken 
setwd("C:/Users/hanna/OneDrive/Dokumente/Master/4.Semester/Ampel/RQs/RQ1/R")

#
normalized_mood <- read.csv("data/normalized_interjectionscore.csv")
normalized_mood$InterjectionScore_norm <- as.numeric(normalized_mood$InterjectionScore_norm)

# Month as factor (month-by-month differences)

# transform Month as numeric to observe overall trend
normalized_mood$MonthDate <- as.Date(paste0(normalized_mood$Month, "-01")) 

# Calculate numeric month index (1 = first month in dataset)
normalized_mood <- normalized_mood[order(normalized_mood$MonthDate), ] 
normalized_mood$MonthNum <- 0:(nrow(normalized_mood)-1)


## plot

# Add 3-month rolling mean for more smoothness
normalized_mood$RollMean <- rollmean(normalized_mood$InterjectionScore_norm, k = 3, fill = NA)

p <- ggplot(normalized_mood, aes(x = MonthDate, y = InterjectionScore_norm)) +
  geom_point(color = "#1f77b4", size = 3) +
  geom_line(color = "#1f77b4", alpha = 0.5) +
  geom_line(aes(y = RollMean), color = "#2ca02c", size = 1) +
  geom_vline(xintercept = as.Date("2024-11-01"), linetype = "dashed", color = "red") +
  scale_x_date(date_labels = "%m %Y", date_breaks = "1 month") +
  labs(
    x = "Month",
    y = "Normalized Interjection Score",
    title = "Interjection Scores Over the Legislative Period",
    subtitle = "Blue points = monthly score; Green line = 3-month rolling average"
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

p
ggsave("out/monthly_trend.png", plot = p, width = 10, height = 6, dpi = 300)

p <- ggplot(normalized_mood, aes(x = MonthDate, y = RollMean)) +
  geom_line(color = "darkgreen", size = 1.2) +
  geom_vline(xintercept = as.Date("2024-11-01"), linetype = "dashed", color = "red") +
  scale_x_date(date_labels = "%m %Y", date_breaks = "1 month") +
  labs(
    x = "Month",
    y = "3-Month Rolling Mean Interjection Score",
    title = "Trend in Coalition Interjections Over the Legislative Period",
    subtitle = "Dashed red line = government breakup (Nov 2024)"
  ) +
  theme_minimal() +
  theme(axis.text.x = element_text(angle = 60, hjust = 1))
p
ggsave("out/monthly_trend_rollingmean.png", plot = p, width = 10, height = 6, dpi = 300)


# month to month changes
normalized_mood$Sign <- ifelse(normalized_mood$InterjectionScore_norm >= 0, "Positive", "Negative")

normalized_mood <- normalized_mood %>%
  arrange(MonthNum) %>%
  mutate(MonthlyChange = InterjectionScore_norm - lag(InterjectionScore_norm))

p<-ggplot(normalized_mood, aes(x = Month, y = MonthlyChange, fill = Sign)) +
  geom_col(width = 0.5) +
  geom_hline(yintercept = 0, linetype = "dashed") +
  geom_text(aes(label = round(InterjectionScore_norm, 1)), 
            vjust = ifelse(normalized_mood$InterjectionScore_norm >= 0, -0.5, 1.5), 
            size = 2) +  
  scale_fill_manual(
    values = c(
      "Positive" = "palegreen3", 
      "Negative" = "firebrick3"
    ),
    labels = c(
      "Positive" = "Cooperative",
      "Negative" = "Confrontational"
    )
  ) +
  theme_minimal() +
  theme(
    axis.text.x = element_text(angle = 45, hjust = 1, size = 6),
    panel.border = element_rect(color = "gray80", fill = NA)
  ) +
  labs(
    x = "Month",
    y = "Monthly Change in Interjection Score",
    fill = "Overall Interjection\nPolarity"
  )
p
ggsave("out/monthly_change.png", plot = p, width = 10, height = 6, dpi = 300)



# Quick line plot of speech_tokens per month
head(normalized_mood)
names(normalized_mood)
library(scales)

ggplot(normalized_mood, aes(x = MonthDate, y = speech_tokens)) +
  geom_line(group = 1, color = "steelblue") +
  geom_point(color = "steelblue") +
  labs(title = "Speech Tokens per Month by FDP, Greens, SPD", x = "Month", y = "Speech Tokens") +
  scale_y_continuous(labels = comma) +
  theme_minimal() +
  theme(axis.text.x = element_text(angle = 45, hjust = 1))
# Research Status in Pedestrian Trajectory Prediction in Unstructured Environments with Human-Vehicle Interactions (Prior to August 2023)

## 1. Introduction
### 1.1. Context and Importance
Pedestrian trajectory prediction is a critical component for autonomous systems operating in human-centric environments, particularly in shared spaces where human-vehicle interactions are prevalent. Accurate prediction of pedestrian movements is essential for ensuring safety, efficiency, and comfort in applications such as autonomous driving, robotics, and intelligent urban planning. The complexity of human behavior, coupled with the dynamic and often unpredictable nature of unstructured environments, poses significant challenges to developing robust prediction models. This survey summarizes the research status in this field prior to August 2023.

### 1.2. Scope of the Survey (Unstructured Environments, Human-Vehicle Interactions, Prior to Aug 2023)
This report focuses specifically on pedestrian trajectory prediction within "unstructured environments," defined as settings lacking strict traffic rules or clear landmarks (e.g., shared spaces, campus areas, off-road settings). A key emphasis is placed on "human-vehicle interactions," analyzing models that explicitly consider the influence of vehicles on pedestrian motion and vice versa. The timeframe for this summary is strictly "prior to August 2023," drawing heavily from the systematic review "Pedestrian Trajectory Prediction in Pedestrian-Vehicle Mixed Environments: A Systematic Review" (2308.06419v1.pdf).

## 2. Dominant Research Trends and Paradigms
### 2.1. Deep Learning Dominance (RNNs, CNNs, GNNs, Generative Models, Transformers)
Prior to August 2023, research in pedestrian trajectory prediction, especially in human-vehicle mixed environments, was heavily dominated by deep learning approaches (2308.06419v1.pdf). Recurrent Neural Networks (RNNs), including Long Short-Term Memory (LSTM) and Gated Recurrent Unit (GRU) networks, were widely employed in encoder-decoder architectures to model sequential pedestrian movements. Convolutional Neural Networks (CNNs) were utilized for extracting spatial features and patterns from input data. Graph Neural Networks (GNNs) and Graph Convolutional Networks (GCNs) emerged as prominent tools for effectively modeling spatio-temporal interactions among multiple agents (pedestrians and vehicles) within a scene. Generative models, such as Generative Adversarial Networks (GANs) and Conditional Variational Autoencoders (CVAEs), played a crucial role in addressing the inherent uncertainty and multimodal nature of pedestrian behavior by generating diverse plausible future trajectories. More recently, Transformer Networks were also increasingly adopted due to their ability to capture long-range dependencies and complex interactions efficiently (2308.06419v1.pdf).

## 3. Categorization of Predictive Models and Methodologies
Predictive models in this domain can be broadly categorized into expert-based, data-driven, and hybrid approaches (2308.06419v1.pdf).

### 3.1. Expert-based Models
These models rely on predefined rules, physics principles, or heuristics to simulate pedestrian behavior. They offer interpretability but may struggle with the complexity and diversity of behaviors in unstructured environments (2308.06419v1.pdf).
#### 3.1.1. Social Force Models (SFM)
SFMs simulate pedestrian movement based on attractive and repulsive forces from goals, obstacles, and other agents. Extensions have been developed to incorporate vehicle interactions (2308.06419v1.pdf).
#### 3.1.2. Kinematic Models
These models predict future positions based on current and past velocities and accelerations, often assuming constant velocity or simple motion patterns (2308.06419v1.pdf).
#### 3.1.3. Game Theory
Game-theoretic approaches model interactions as strategic decision-making processes, where agents optimize their actions based on the predicted actions of others, particularly relevant for human-vehicle negotiation scenarios (2308.06419v1.pdf).
#### 3.1.4. Cellular Automata
Cellular automata models represent the environment as a grid and update agent positions based on local rules, providing a discrete simulation of movement (2308.06419v1.pdf).

### 3.2. Data-driven Models (Primarily Deep Learning)
Data-driven models learn patterns directly from observed data, with deep learning methods being the most prevalent due to their ability to handle complex, non-linear relationships and multimodal predictions (2308.06419v1.pdf).
#### 3.2.1. Recurrent Neural Networks (RNNs, LSTMs/GRUs)
RNNs, particularly LSTMs and GRUs, are well-suited for processing sequential data like trajectories. They are commonly used in encoder-decoder architectures, where an encoder learns a representation of past trajectories and an decoder predicts future ones (2308.06419v1.pdf).
#### 3.2.2. Convolutional Neural Networks (CNNs)
CNNs are often used to extract spatial features from grid-based representations of the environment or agent interactions, capturing local patterns that influence movement (2308.06419v1.pdf).
#### 3.2.3. Graph Neural Networks (GNNs/GCNs)
GNNs and GCNs have become highly effective for modeling spatio-temporal interactions in multi-agent scenes. They represent agents as nodes in a graph and interactions as edges, allowing for the propagation of information across the network (2308.06419v1.pdf).
#### 3.2.4. Generative Models (GANs, CVAEs)
Generative models like GANs and CVAEs are crucial for addressing the inherent uncertainty in pedestrian behavior. They can generate multiple plausible future trajectories, providing a distribution of possible outcomes rather than a single deterministic prediction (2308.06419v1.pdf).
#### 3.2.5. Transformer Networks
Transformer networks, originally developed for natural language processing, have been increasingly applied to trajectory prediction due to their self-attention mechanism, which can effectively capture long-range dependencies and complex interactions between agents over time (2308.06419v1.pdf).
#### 3.2.6. Other Data-driven Approaches (DBN, Linear Regression, RL)
Other data-driven methods include Dynamic Bayesian Networks (DBN) for probabilistic modeling, Linear Regression for simpler scenarios, and Reinforcement Learning (RL) where agents learn optimal policies through interaction with the environment (2308.06419v1.pdf).

### 3.3. Hybrid Models
Hybrid models combine the strengths of both expert-based and data-driven approaches. For instance, they might use physics-based constraints within a deep learning framework or calibrate expert models with real-world data to improve both accuracy and interpretability (2308.06419v1.pdf).

## 4. Key Datasets
The availability of relevant datasets is critical for training and evaluating trajectory prediction models.
### 4.1. Datasets for Unstructured/Shared Spaces with Human-Vehicle Interactions
There is a noted scarcity of publicly available datasets specifically for truly unstructured/shared spaces with diverse pedestrian-vehicle interactions. Examples include SDD (Stanford Drone Dataset), HBS (High-Density Bottleneck Scenarios), HC (Honda Campus Dataset), DUT (Dalian University of Technology), CITR (Center for Intelligent Transportation Research), Nantes, USyd (University of Sydney), and various university/public space datasets (2308.06419v1.pdf).
### 4.2. Datasets for Conventional Road Environments
More datasets exist for conventional road environments, which often feature structured traffic rules but may still include pedestrian interactions. These include inD, INTERACTION, RounD, MOT (Multiple Object Tracking), TRAF, LOKI, Argoverse, Waymo, nuScenes, BLVD, KITTI, ApolloScape, Euro-PVI, IVBP, PedX, PIE, JAAD, DAIL, BJI, and TJI (2308.06419v1.pdf).

## 5. Evaluation Metrics
Evaluation metrics are crucial for assessing the performance of prediction models.
### 5.1. General Performance Metrics
Common general performance metrics compare predicted and real trajectories, such as Average Displacement Error (ADE) and Final Displacement Error (FDE), which measure the average and final Euclidean distances between predicted and ground-truth paths (2308.06419v1.pdf).
### 5.2. Social Awareness Metrics
There is a recognized need for richer metrics that measure social awareness, such as collision avoidance and adherence to social norms, which are particularly important in interactive environments (2308.06419v1.pdf).
### 5.3. Collision-Related Metrics (TrajNet++)
The TrajNet++ benchmark is highlighted for introducing novel collision-related metrics to better evaluate collision avoidance capabilities in interactive scenarios, moving beyond purely geometric accuracy to assess safety aspects (2308.06419v1.pdf).

## 6. Common Challenges and Limitations
Despite significant progress, several challenges and limitations persist in the field (2308.06419v1.pdf).
### 6.1. Limited Datasets
A significant scarcity of publicly available datasets specifically designed for truly unstructured/shared spaces with diverse and complex human-vehicle interactions remains a major hurdle.
### 6.2. Interpretability vs. Accuracy Trade-off
Deep learning models, while achieving high accuracy, often lack interpretability, making it difficult to understand their decision-making process, which is a critical concern for safety-critical applications like autonomous driving.
### 6.3. Insufficient Interaction Features
Many data-driven methods tend to over-rely on simple relative distance for interaction modeling, neglecting richer and more nuanced cues such as relative speed, approach direction, gaze, body posture, or collision risk.
### 6.4. Lack of Active Prediction
Models often predict pedestrian trajectories passively, without explicitly considering how pedestrians might actively respond to future vehicle actions, intentions, or changes in the environment.
### 6.5. Disregard for Pedestrian Diversity
Many current models assume homogeneous pedestrian behavior, overlooking individual differences in walking styles, intentions, cognitive states, and risk perception, which can significantly impact trajectory.
### 6.6. Absence of Standardized Benchmarks
A lack of common benchmarks specifically designed for evaluating heterogeneous interaction types in shared or unstructured spaces hinders effective and fair comparison among different models.

## 7. Key Breakthroughs and Significant Advancements
### 7.1. Dominance of Deep Learning
The widespread adoption and advancements in deep learning architectures have enabled more accurate and sophisticated modeling of complex spatio-temporal interactions between pedestrians and vehicles (2308.06419v1.pdf).
### 7.2. Multimodal Prediction
The development and application of generative models (GANs, CVAEs) have been instrumental in achieving multimodal prediction, allowing models to generate a distribution of plausible future trajectories and better capture the inherent uncertainty in human behavior (2308.06419v1.pdf).
### 7.3. Enhanced Interaction Modeling (GNNs)
Graph Neural Networks (GNNs) have significantly improved the ability to model complex interactions within multi-agent scenes, effectively capturing the relational dynamics between pedestrians and vehicles (2308.06419v1.pdf).
### 7.4. Focus on Interpretability
There is a growing emphasis on developing more interpretable prediction models, particularly for safety-critical applications, moving towards explainable AI to increase trust and reliability (2308.06419v1.pdf).
### 7.5. New Evaluation Metrics (TrajNet++)
Benchmarks like TrajNet++ have introduced novel collision-related metrics, which provide a more comprehensive evaluation of models' collision avoidance capabilities in interactive scenarios, addressing the limitations of purely geometric metrics (2308.06419v1.pdf).

## 8. Future Research Directions (Educated Guesses)
### 8.1. Overcoming Data Limitations (Transfer Learning, Synthetic Data, Few-shot Learning)
Given the persistent challenge of data scarcity in truly unstructured environments with human-vehicle interactions, future research will likely place a strong emphasis on **transfer learning, synthetic data generation, and self-supervised or few-shot learning techniques** to overcome data limitations.
### 8.2. Integrating Cognitive Models and Intent Recognition
Furthermore, there will be an increased focus on integrating **cognitive models, psychological insights, or explicit intent recognition** into deep learning architectures to better capture human decision-making and active responses, moving beyond purely kinematic observations.
### 8.3. Multi-agent Reinforcement Learning (MARL) for Proactive Prediction
Additionally, given the complexity of human-vehicle interactions in unstructured environments and the challenges of interpretability, active prediction, and pedestrian diversity, future research will likely move towards **multi-agent reinforcement learning (MARL) approaches that explicitly model interaction strategies and intentions of both pedestrians and vehicles in a game-theoretic manner**, allowing for more proactive and adaptable prediction and decision-making.

## 9. Conclusion
Prior to August 2023, the field of pedestrian trajectory prediction in unstructured environments with human-vehicle interactions was characterized by the dominance of deep learning approaches, particularly RNNs, CNNs, GNNs, and generative models, for their ability to handle complex spatio-temporal interactions and multimodal outputs. While significant advancements were made in interaction modeling and multimodal prediction, challenges such as limited datasets, the interpretability-accuracy trade-off, insufficient interaction features, and the lack of active prediction and standardized benchmarks persisted. Future research is expected to focus on data augmentation strategies like transfer learning and synthetic data, as well as integrating cognitive models and multi-agent reinforcement learning to achieve more robust, interpretable, and proactive prediction capabilities in these complex environments.

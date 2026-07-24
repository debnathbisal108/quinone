import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return Scaffold(
      body: CustomScrollView(
        slivers: [
          SliverAppBar(
            pinned: true,
            expandedHeight: 130,
            elevation: 0,
            backgroundColor: scheme.surface,
            flexibleSpace: FlexibleSpaceBar(
              titlePadding: const EdgeInsets.only(
                left: 20,
                bottom: 16,
              ),
              title: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    "Good Morning",
                    style: theme.textTheme.labelLarge,
                  ),
                  Text(
                    "Guest",
                    style: theme.textTheme.titleLarge,
                  ),
                ],
              ),
            ),
          ),

          SliverPadding(
            padding: const EdgeInsets.all(20),
            sliver: SliverList(
              delegate: SliverChildListDelegate(
                [
                  Hero(
                    tag: "analyze_food",
                    child: Material(
                      color: Colors.transparent,
                      child: InkWell(
                        borderRadius:
                            BorderRadius.circular(28),
                        onTap: () {
                          context.push("/upload");
                        },
                        child: Ink(
                          decoration: BoxDecoration(
                            borderRadius:
                                BorderRadius.circular(28),
                            gradient: LinearGradient(
                              colors: [
                                Colors.teal.shade700,
                                Colors.green.shade500,
                              ],
                            ),
                          ),
                          child: Padding(
                            padding:
                                const EdgeInsets.all(26),
                            child: Column(
                              crossAxisAlignment:
                                  CrossAxisAlignment.start,
                              children: [
                                Container(
                                  padding:
                                      const EdgeInsets.all(
                                    14,
                                  ),
                                  decoration:
                                      BoxDecoration(
                                    color: Colors.white24,
                                    borderRadius:
                                        BorderRadius
                                            .circular(
                                      18,
                                    ),
                                  ),
                                  child: const Icon(
                                    Icons.restaurant,
                                    color: Colors.white,
                                    size: 34,
                                  ),
                                ),

                                const SizedBox(
                                  height: 26,
                                ),

                                Text(
                                  "Analyze Food",
                                  style: theme
                                      .textTheme
                                      .headlineMedium
                                      ?.copyWith(
                                    color:
                                        Colors.white,
                                    fontWeight:
                                        FontWeight.bold,
                                  ),
                                ),

                                const SizedBox(
                                  height: 10,
                                ),

                                const Text(
                                  "Capture your meal or upload multiple food images for complete nutritional analysis.",
                                  style: TextStyle(
                                    color:
                                        Colors.white70,
                                    fontSize: 15,
                                  ),
                                ),

                                const SizedBox(
                                  height: 28,
                                ),

                                Row(
                                  children: [
                                    FilledButton.icon(
                                      style:
                                          FilledButton
                                              .styleFrom(
                                        backgroundColor:
                                            Colors.white,
                                        foregroundColor:
                                            Colors.teal,
                                      ),
                                      onPressed: () {
                                        context.push(
                                            "/upload");
                                      },
                                      icon: const Icon(
                                        Icons
                                            .camera_alt_rounded,
                                      ),
                                      label: const Text(
                                        "Start",
                                      ),
                                    ),
                                  ],
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),

                  const SizedBox(height: 30),

                  Text(
                    "Today's Summary",
                    style:
                        theme.textTheme.headlineSmall,
                  ),

                  const SizedBox(height: 18),

                  Row(
                    children: [
                      Expanded(
                        child: _StatCard(
                          title: "Calories",
                          value: "--",
                          icon: Icons.local_fire_department,
                          color: Colors.orange,
                        ),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: _StatCard(
                          title: "Protein",
                          value: "--",
                          icon: Icons.fitness_center,
                          color: Colors.green,
                        ),
                      ),
                    ],
                  ),

                  const SizedBox(height: 14),

                  Row(
                    children: [
                      Expanded(
                        child: _StatCard(
                          title: "Meals",
                          value: "0",
                          icon: Icons.restaurant_menu,
                          color: Colors.teal,
                        ),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: _StatCard(
                          title: "Health",
                          value: "--",
                          icon: Icons.favorite,
                          color: Colors.red,
                        ),
                      ),
                    ],
                  ),

                  const SizedBox(height: 34),

                  Text(
                    "Recent Analyses",
                    style:
                        theme.textTheme.headlineSmall,
                  ),

                  const SizedBox(height: 16),

                  Card(
                    elevation: 0,
                    shape: RoundedRectangleBorder(
                      borderRadius:
                          BorderRadius.circular(22),
                    ),
                    child: const Padding(
                      padding: EdgeInsets.all(26),
                      child: Center(
                        child: Text(
                          "No analyses yet.\nAnalyze your first meal.",
                          textAlign: TextAlign.center,
                        ),
                      ),
                    ),
                  ),

                  const SizedBox(height: 28),

                  Card(
                    elevation: 0,
                    color: Colors.amber.shade50,
                    shape: RoundedRectangleBorder(
                      borderRadius:
                          BorderRadius.circular(22),
                    ),
                    child: const Padding(
                      padding: EdgeInsets.all(22),
                      child: Row(
                        crossAxisAlignment:
                            CrossAxisAlignment.start,
                        children: [
                          Icon(
                            Icons.lightbulb,
                            color: Colors.amber,
                          ),
                          SizedBox(width: 14),
                          Expanded(
                            child: Text(
                              "Tip: Capture the entire meal clearly. If a branded product is detected, Quinone may request a photo of its Nutrition Facts label.",
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),

                  const SizedBox(height: 40),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  final String title;
  final String value;
  final IconData icon;
  final Color color;

  const _StatCard({
    required this.title,
    required this.value,
    required this.icon,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(22),
      ),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          children: [
            CircleAvatar(
              radius: 24,
              backgroundColor:
                  color.withOpacity(.12),
              child: Icon(
                icon,
                color: color,
              ),
            ),
            const SizedBox(height: 16),
            Text(
              value,
              style:
                  Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 6),
            Text(title),
          ],
        ),
      ),
    );
  }
}